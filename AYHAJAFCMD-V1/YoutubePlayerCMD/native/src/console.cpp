#include "console.hpp"

#include <csignal>

#ifdef _WIN32
#define NOMINMAX
#include <windows.h>
#include <conio.h>
#else
#include <fcntl.h>
#include <sys/ioctl.h>
#include <termios.h>
#include <unistd.h>
#include <cerrno>

struct Console::State {
    termios oldMode{};
    bool hasOldMode = false;
};
#endif

namespace {
volatile std::sig_atomic_t gInterrupted = 0;

#ifdef _WIN32
BOOL WINAPI consoleControlHandler(DWORD event) {
    if (event == CTRL_C_EVENT || event == CTRL_BREAK_EVENT || event == CTRL_CLOSE_EVENT) {
        gInterrupted = 1;
        return TRUE;
    }
    return FALSE;
}
#else
void interruptHandler(int) {
    gInterrupted = 1;
}
#endif
}

void installInterruptHandler() {
#ifdef _WIN32
    SetConsoleCtrlHandler(consoleControlHandler, TRUE);
#else
    std::signal(SIGINT, interruptHandler);
#endif
}

bool interruptionRequested() {
    return gInterrupted != 0;
}

Console::Console(bool takeOverScreen) {
#ifdef _WIN32
    HANDLE output = GetStdHandle(STD_OUTPUT_HANDLE);
    HANDLE input = GetStdHandle(STD_INPUT_HANDLE);
    DWORD outputMode = 0;
    DWORD inputMode = 0;
    if (output != INVALID_HANDLE_VALUE && GetConsoleMode(output, &outputMode)) {
        outputHandle_ = output;
        oldOutputMode_ = outputMode;
        SetConsoleMode(output, outputMode | ENABLE_VIRTUAL_TERMINAL_PROCESSING);
    }
    if (takeOverScreen && input != INVALID_HANDLE_VALUE && GetConsoleMode(input, &inputMode)) {
        oldInputMode_ = inputMode;
        SetConsoleMode(input, inputMode & ~(ENABLE_ECHO_INPUT | ENABLE_LINE_INPUT));
    }
    active_ = takeOverScreen && outputHandle_ != nullptr;
#else
    inputHandle_ = takeOverScreen ? open("/dev/tty", O_RDONLY | O_NONBLOCK) : -1;
    if (inputHandle_ >= 0) {
        ownsInputHandle_ = true;
    } else {
        inputHandle_ = STDIN_FILENO;
    }
    state_ = new State;
    if (takeOverScreen && tcgetattr(inputHandle_, &state_->oldMode) == 0) {
        termios raw = state_->oldMode;
        raw.c_lflag &= static_cast<tcflag_t>(~(ICANON | ECHO));
        raw.c_cc[VMIN] = 0;
        raw.c_cc[VTIME] = 0;
        tcsetattr(inputHandle_, TCSANOW, &raw);
        state_->hasOldMode = true;
        active_ = true;
    }
#endif
    if (active_) {
        write("\x1b[?25l\x1b[?1049h\x1b[2J\x1b[H");
    }
}

Console::~Console() {
    if (active_) {
        write("\x1b[0m\x1b[?25h\x1b[?1049l");
    }
#ifdef _WIN32
    HANDLE output = static_cast<HANDLE>(outputHandle_);
    if (output != nullptr) {
        SetConsoleMode(output, oldOutputMode_);
    }
    HANDLE input = GetStdHandle(STD_INPUT_HANDLE);
    if (input != INVALID_HANDLE_VALUE && oldInputMode_ != 0) {
        SetConsoleMode(input, oldInputMode_);
    }
#else
    if (state_ != nullptr && state_->hasOldMode) {
        tcsetattr(inputHandle_, TCSANOW, &state_->oldMode);
    }
    if (ownsInputHandle_ && inputHandle_ >= 0) {
        close(inputHandle_);
    }
    delete state_;
#endif
}

TerminalSize Console::size() const {
#ifdef _WIN32
    CONSOLE_SCREEN_BUFFER_INFO info{};
    HANDLE output = static_cast<HANDLE>(outputHandle_);
    if (output != nullptr && GetConsoleScreenBufferInfo(output, &info)) {
        return {info.srWindow.Right - info.srWindow.Left + 1,
                info.srWindow.Bottom - info.srWindow.Top + 1};
    }
#else
    winsize info{};
    if (ioctl(STDOUT_FILENO, TIOCGWINSZ, &info) == 0 && info.ws_col > 0 && info.ws_row > 0) {
        return {info.ws_col, info.ws_row};
    }
#endif
    return {80, 24};
}

Key Console::pollKey() const {
#ifdef _WIN32
    if (!_kbhit()) {
        return Key::None;
    }
    int value = _getch();
    if (value == 0 || value == 0xe0) {
        switch (_getch()) {
            case 0x4b: return Key::Left;
            case 0x4d: return Key::Right;
            case 0x48: return Key::Up;
            case 0x50: return Key::Down;
            default: return Key::None;
        }
    }
#else
    unsigned char value = 0;
    if (read(inputHandle_, &value, 1) != 1) {
        return Key::None;
    }
    if (value == 0x1b) {
        unsigned char sequence[2]{};
        if (read(inputHandle_, sequence, sizeof(sequence)) == 2 && sequence[0] == '[') {
            switch (sequence[1]) {
                case 'A': return Key::Up;
                case 'B': return Key::Down;
                case 'C': return Key::Right;
                case 'D': return Key::Left;
                default: return Key::None;
            }
        }
        return Key::Quit;
    }
#endif
    switch (value) {
        case 'q': case 'Q': return Key::Quit;
        case ' ': return Key::Pause;
        case 'r': case 'R': return Key::Restart;
        case '+': case '=': return Key::QualityUp;
        case '-': return Key::QualityDown;
        case 'f': case 'F': return Key::Fullscreen;
        default: return Key::None;
    }
}

void Console::write(const std::string& text) const {
#ifdef _WIN32
    HANDLE output = static_cast<HANDLE>(outputHandle_);
    if (output != nullptr) {
        DWORD written = 0;
        WriteFile(output, text.data(), static_cast<DWORD>(text.size()), &written, nullptr);
    } else {
        DWORD written = 0;
        WriteFile(GetStdHandle(STD_OUTPUT_HANDLE), text.data(),
                  static_cast<DWORD>(text.size()), &written, nullptr);
    }
#else
    const char* next = text.data();
    size_t remaining = text.size();
    while (remaining > 0) {
        ssize_t written = ::write(STDOUT_FILENO, next, remaining);
        if (written <= 0) {
            if (written < 0 && errno == EINTR) continue;
            break;
        }
        next += written;
        remaining -= static_cast<size_t>(written);
    }
#endif
}

void Console::clear() const {
    write("\x1b[2J\x1b[H");
}