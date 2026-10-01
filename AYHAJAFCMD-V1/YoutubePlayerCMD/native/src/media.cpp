#include "media.hpp"
#include "console.hpp"

#ifdef _WIN32
#define NOMINMAX
#include <windows.h>
#else
#include <cerrno>
#include <csignal>
#include <fcntl.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <unistd.h>
#endif

#include <chrono>
#include <thread>

#ifdef _WIN32
namespace {
std::string quoteArgument(const std::string& argument) {
    std::string result = "\"";
    size_t slashes = 0;
    for (char value : argument) {
        if (value == '\\') {
            ++slashes;
        } else if (value == '"') {
            result.append(slashes * 2 + 1, '\\');
            result.push_back(value);
            slashes = 0;
        } else {
            result.append(slashes, '\\');
            slashes = 0;
            result.push_back(value);
        }
    }
    result.append(slashes * 2, '\\');
    result.push_back('"');
    return result;
}
}
#endif

ChildProcess::~ChildProcess() {
    stop();
}

bool ChildProcess::start(const std::vector<std::string>& arguments, bool captureOutput) {
    stop();
    if (arguments.empty()) return false;
#ifdef _WIN32
    SECURITY_ATTRIBUTES security{};
    security.nLength = sizeof(security);
    security.bInheritHandle = TRUE;
    HANDLE readPipe = nullptr;
    HANDLE writePipe = nullptr;
    if (captureOutput && !CreatePipe(&readPipe, &writePipe, &security, 0)) return false;
    if (captureOutput) SetHandleInformation(readPipe, HANDLE_FLAG_INHERIT, 0);

    HANDLE nullInput = CreateFileA("NUL", GENERIC_READ, FILE_SHARE_READ | FILE_SHARE_WRITE,
                                   &security, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, nullptr);
    HANDLE nullOutput = CreateFileA("NUL", GENERIC_WRITE, FILE_SHARE_READ | FILE_SHARE_WRITE,
                                    &security, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, nullptr);
    STARTUPINFOA startup{};
    startup.cb = sizeof(startup);
    startup.dwFlags = STARTF_USESTDHANDLES;
    startup.hStdInput = nullInput;
    startup.hStdOutput = captureOutput ? writePipe : nullOutput;
    startup.hStdError = nullOutput;
    PROCESS_INFORMATION process{};
    std::string command;
    for (const auto& argument : arguments) {
        if (!command.empty()) command.push_back(' ');
        command += quoteArgument(argument);
    }
    const BOOL created = CreateProcessA(nullptr, command.data(), nullptr, nullptr, TRUE,
                                        CREATE_NO_WINDOW, nullptr, nullptr, &startup, &process);
    if (writePipe != nullptr) CloseHandle(writePipe);
    if (nullInput != INVALID_HANDLE_VALUE) CloseHandle(nullInput);
    if (nullOutput != INVALID_HANDLE_VALUE) CloseHandle(nullOutput);
    if (!created) {
        if (readPipe != nullptr) CloseHandle(readPipe);
        return false;
    }
    CloseHandle(process.hThread);
    processHandle_ = process.hProcess;
    outputHandle_ = captureOutput ? readPipe : nullptr;
    return true;
#else
    int descriptors[2] = {-1, -1};
    if (captureOutput && pipe(descriptors) != 0) return false;
    const pid_t child = fork();
    if (child < 0) {
        if (captureOutput) { close(descriptors[0]); close(descriptors[1]); }
        return false;
    }
    if (child == 0) {
        if (captureOutput) {
            dup2(descriptors[1], STDOUT_FILENO);
            close(descriptors[0]);
            close(descriptors[1]);
        } else {
            const int nullOutput = open("/dev/null", O_WRONLY);
            if (nullOutput >= 0) dup2(nullOutput, STDOUT_FILENO);
        }
        const int nullInput = open("/dev/null", O_RDONLY);
        const int nullError = open("/dev/null", O_WRONLY);
        if (nullInput >= 0) dup2(nullInput, STDIN_FILENO);
        if (nullError >= 0) dup2(nullError, STDERR_FILENO);
        std::vector<char*> values;
        values.reserve(arguments.size() + 1);
        for (const auto& argument : arguments) values.push_back(const_cast<char*>(argument.c_str()));
        values.push_back(nullptr);
        execvp(values[0], values.data());
        _exit(127);
    }
    if (captureOutput) {
        close(descriptors[1]);
        outputHandle_ = descriptors[0];
    }
    processId_ = static_cast<int>(child);
    return true;
#endif
}

bool ChildProcess::readExact(unsigned char* buffer, size_t size) {
    size_t offset = 0;
    while (offset < size) {
        if (interruptionRequested()) return false;
#ifdef _WIN32
        DWORD readCount = 0;
        HANDLE output = static_cast<HANDLE>(outputHandle_);
        if (output == nullptr || !ReadFile(output, buffer + offset,
                static_cast<DWORD>(size - offset), &readCount, nullptr) || readCount == 0) return false;
        offset += readCount;
#else
        if (outputHandle_ < 0) return false;
        ssize_t readCount = read(outputHandle_, buffer + offset, size - offset);
        if (readCount == 0) return false;
        if (readCount < 0) {
            if (errno == EINTR && !interruptionRequested()) continue;
            return false;
        }
        offset += static_cast<size_t>(readCount);
#endif
    }
    return true;
}

bool ChildProcess::running() {
#ifdef _WIN32
    if (processHandle_ == nullptr) return false;
    DWORD code = 0;
    return GetExitCodeProcess(static_cast<HANDLE>(processHandle_), &code) && code == STILL_ACTIVE;
#else
    if (processId_ < 0) return false;
    int status = 0;
    const pid_t result = waitpid(processId_, &status, WNOHANG);
    if (result == 0) return true;
    processId_ = -1;
    return false;
#endif
}

void ChildProcess::stop() {
#ifdef _WIN32
    if (processHandle_ != nullptr) {
        HANDLE process = static_cast<HANDLE>(processHandle_);
        if (WaitForSingleObject(process, 0) == WAIT_TIMEOUT) {
            TerminateProcess(process, 0);
            WaitForSingleObject(process, 1000);
        }
        CloseHandle(process);
        processHandle_ = nullptr;
    }
    if (outputHandle_ != nullptr) {
        CloseHandle(static_cast<HANDLE>(outputHandle_));
        outputHandle_ = nullptr;
    }
#else
    if (processId_ >= 0) {
        kill(processId_, SIGTERM);
        for (int attempt = 0; attempt < 100; ++attempt) {
            int status = 0;
            const pid_t result = waitpid(processId_, &status, WNOHANG);
            if (result == processId_ || (result < 0 && errno == ECHILD)) {
                processId_ = -1;
                break;
            }
            std::this_thread::sleep_for(std::chrono::milliseconds(10));
        }
        if (processId_ >= 0) {
            kill(processId_, SIGKILL);
            waitpid(processId_, nullptr, 0);
            processId_ = -1;
        }
    }
    if (outputHandle_ >= 0) {
        close(outputHandle_);
        outputHandle_ = -1;
    }
#endif
}