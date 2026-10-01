#pragma once

#include <string>
#include <vector>

class ChildProcess {
public:
    ChildProcess() = default;
    ~ChildProcess();
    ChildProcess(const ChildProcess&) = delete;
    ChildProcess& operator=(const ChildProcess&) = delete;

    bool start(const std::vector<std::string>& arguments, bool captureOutput);
    bool readExact(unsigned char* buffer, size_t size);
    bool running();
    void stop();

private:
#ifdef _WIN32
    void* processHandle_ = nullptr;
    void* outputHandle_ = nullptr;
#else
    int processId_ = -1;
    int outputHandle_ = -1;
#endif
};