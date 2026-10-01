#pragma once

#include <string>

struct TerminalSize {
    int columns;
    int rows;
};

void installInterruptHandler();
bool interruptionRequested();

enum class Key {
    None,
    Quit,
    Pause,
    Left,
    Right,
    Up,
    Down,
    Restart,
    QualityUp,
    QualityDown,
    Fullscreen,
};

class Console {
public:
    explicit Console(bool takeOverScreen = true);
    ~Console();
    Console(const Console&) = delete;
    Console& operator=(const Console&) = delete;

    TerminalSize size() const;
    Key pollKey() const;
    void write(const std::string& text) const;
    void clear() const;

private:
    bool active_ = false;
#ifdef _WIN32
    void* outputHandle_ = nullptr;
    unsigned long oldOutputMode_ = 0;
    unsigned long oldInputMode_ = 0;
#else
    int inputHandle_ = -1;
    bool ownsInputHandle_ = false;
    struct State;
    State* state_ = nullptr;
#endif
};