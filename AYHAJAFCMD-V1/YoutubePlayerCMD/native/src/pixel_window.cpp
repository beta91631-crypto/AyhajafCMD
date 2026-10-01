#include "pixel_window.hpp"

#include <algorithm>
#include <cstddef>
#include <cstdint>
#include <deque>
#include <string>
#include <vector>

#ifdef _WIN32
#define NOMINMAX
#include <windows.h>
#endif

struct PixelWindowState {
#ifdef _WIN32
    HWND window = nullptr;
    std::vector<unsigned char> bgra;
    int frameWidth = 0;
    int frameHeight = 0;
    std::deque<Key> keys;
#endif
    bool closed = false;
};

#ifdef _WIN32
namespace {
constexpr wchar_t kWindowClass[] = L"YouTubeCMDPixelWindow";

std::wstring toWide(const std::string& text) {
    if (text.empty()) return {};
    const int length = MultiByteToWideChar(CP_UTF8, 0, text.c_str(), -1, nullptr, 0);
    if (length <= 1) return L"YouTubeCMD";
    std::wstring result(static_cast<size_t>(length), L'\0');
    MultiByteToWideChar(CP_UTF8, 0, text.c_str(), -1, result.data(), length);
    result.resize(static_cast<size_t>(length - 1));
    return result;
}

void queueKey(PixelWindowState& state, WPARAM value) {
    Key key = Key::None;
    switch (value) {
        case VK_ESCAPE: case 'Q': key = Key::Quit; break;
        case VK_SPACE: key = Key::Pause; break;
        case VK_LEFT: key = Key::Left; break;
        case VK_RIGHT: key = Key::Right; break;
        case VK_UP: key = Key::Up; break;
        case VK_DOWN: key = Key::Down; break;
        case 'R': key = Key::Restart; break;
        case VK_OEM_PLUS: case VK_ADD: key = Key::QualityUp; break;
        case VK_OEM_MINUS: case VK_SUBTRACT: key = Key::QualityDown; break;
        case 'F': key = Key::Fullscreen; break;
        default: break;
    }
    if (key != Key::None) state.keys.push_back(key);
}

void paintFrame(PixelWindowState& state, HWND window, HDC device,
                const RECT& client) {
    FillRect(device, &client, reinterpret_cast<HBRUSH>(GetStockObject(BLACK_BRUSH)));
    if (state.frameWidth < 1 || state.frameHeight < 1 || state.bgra.empty()) return;

    const int clientWidth = client.right - client.left;
    const int clientHeight = client.bottom - client.top;
    const double scale = std::min(
        static_cast<double>(clientWidth) / state.frameWidth,
        static_cast<double>(clientHeight) / state.frameHeight);
    const int drawWidth = std::max(1, static_cast<int>(state.frameWidth * scale));
    const int drawHeight = std::max(1, static_cast<int>(state.frameHeight * scale));
    const int left = client.left + (clientWidth - drawWidth) / 2;
    const int top = client.top + (clientHeight - drawHeight) / 2;

    BITMAPINFO bitmap{};
    bitmap.bmiHeader.biSize = sizeof(BITMAPINFOHEADER);
    bitmap.bmiHeader.biWidth = state.frameWidth;
    bitmap.bmiHeader.biHeight = -state.frameHeight;
    bitmap.bmiHeader.biPlanes = 1;
    bitmap.bmiHeader.biBitCount = 32;
    bitmap.bmiHeader.biCompression = BI_RGB;
    SetStretchBltMode(device, COLORONCOLOR);
    StretchDIBits(device, left, top, drawWidth, drawHeight, 0, 0,
                  state.frameWidth, state.frameHeight, state.bgra.data(),
                  &bitmap, DIB_RGB_COLORS, SRCCOPY);
    (void)window;
}

LRESULT CALLBACK windowProcedure(HWND window, UINT message,
                                 WPARAM value, LPARAM detail) {
    auto* state = reinterpret_cast<PixelWindowState*>(
        GetWindowLongPtrW(window, GWLP_USERDATA));
    if (message == WM_NCCREATE) {
        const auto* create = reinterpret_cast<const CREATESTRUCTW*>(detail);
        state = static_cast<PixelWindowState*>(create->lpCreateParams);
        SetWindowLongPtrW(window, GWLP_USERDATA,
                          reinterpret_cast<LONG_PTR>(state));
    }
    if (state == nullptr) return DefWindowProcW(window, message, value, detail);

    switch (message) {
        case WM_PAINT: {
            PAINTSTRUCT paint{};
            HDC device = BeginPaint(window, &paint);
            RECT client{};
            GetClientRect(window, &client);
            paintFrame(*state, window, device, client);
            EndPaint(window, &paint);
            return 0;
        }
        case WM_ERASEBKGND:
            return 1;
        case WM_KEYDOWN:
            if ((detail & (1L << 30)) == 0) queueKey(*state, value);
            return 0;
        case WM_CLOSE:
            DestroyWindow(window);
            return 0;
        case WM_DESTROY:
            state->closed = true;
            state->window = nullptr;
            PostQuitMessage(0);
            return 0;
        default:
            return DefWindowProcW(window, message, value, detail);
    }
}
}
#endif

PixelWindow::PixelWindow() : state_(new PixelWindowState) {}

PixelWindow::~PixelWindow() {
#ifdef _WIN32
    if (state_->window != nullptr) DestroyWindow(state_->window);
#endif
    delete state_;
}

bool PixelWindow::create(const std::string& title) {
#ifdef _WIN32
    HINSTANCE instance = GetModuleHandleW(nullptr);
    WNDCLASSEXW windowClass{};
    windowClass.cbSize = sizeof(windowClass);
    windowClass.style = CS_HREDRAW | CS_VREDRAW;
    windowClass.lpfnWndProc = windowProcedure;
    windowClass.hInstance = instance;
    windowClass.hCursor = LoadCursorW(nullptr, MAKEINTRESOURCEW(32512));
    windowClass.lpszClassName = kWindowClass;
    if (RegisterClassExW(&windowClass) == 0 &&
        GetLastError() != ERROR_CLASS_ALREADY_EXISTS) {
        return false;
    }

    RECT bounds{0, 0, 960, 540};
    const DWORD style = WS_OVERLAPPEDWINDOW;
    AdjustWindowRect(&bounds, style, FALSE);
    state_->window = CreateWindowExW(
        0, kWindowClass, toWide(title).c_str(), style, CW_USEDEFAULT,
        CW_USEDEFAULT, bounds.right - bounds.left, bounds.bottom - bounds.top,
        nullptr, nullptr, instance, state_);
    if (state_->window == nullptr) return false;
    ShowWindow(state_->window, SW_SHOW);
    UpdateWindow(state_->window);
    return true;
#else
    (void)title;
    return false;
#endif
}

bool PixelWindow::closed() const {
    return state_->closed;
}

TerminalSize PixelWindow::size() const {
#ifdef _WIN32
    RECT client{};
    if (state_->window != nullptr && GetClientRect(state_->window, &client)) {
        return {static_cast<int>(std::max(1L, client.right - client.left)),
            static_cast<int>(std::max(1L, client.bottom - client.top))};
    }
#endif
    return {80, 24};
}

Key PixelWindow::pollKey() {
#ifdef _WIN32
    MSG message{};
    while (PeekMessageW(&message, nullptr, 0, 0, PM_REMOVE)) {
        if (message.message == WM_QUIT) {
            state_->closed = true;
        } else {
            TranslateMessage(&message);
            DispatchMessageW(&message);
        }
    }
    if (!state_->keys.empty()) {
        const Key key = state_->keys.front();
        state_->keys.pop_front();
        return key;
    }
    if (state_->closed) return Key::Quit;
#endif
    return Key::None;
}

void PixelWindow::drawFrame(const unsigned char* rgb, int width, int height) {
#ifdef _WIN32
    if (rgb == nullptr || width < 1 || height < 1 || state_->window == nullptr) return;
    state_->frameWidth = width;
    state_->frameHeight = height;
    state_->bgra.resize(static_cast<size_t>(width) * height * 4);
    for (size_t pixel = 0; pixel < static_cast<size_t>(width) * height; ++pixel) {
        state_->bgra[pixel * 4] = rgb[pixel * 3 + 2];
        state_->bgra[pixel * 4 + 1] = rgb[pixel * 3 + 1];
        state_->bgra[pixel * 4 + 2] = rgb[pixel * 3];
        state_->bgra[pixel * 4 + 3] = 0;
    }
    InvalidateRect(state_->window, nullptr, FALSE);
    UpdateWindow(state_->window);
#else
    (void)rgb;
    (void)width;
    (void)height;
#endif
}

void PixelWindow::setTitle(const std::string& title) const {
#ifdef _WIN32
    if (state_->window != nullptr) SetWindowTextW(state_->window, toWide(title).c_str());
#else
    (void)title;
#endif
}

void PixelWindow::maximize(bool enabled) const {
#ifdef _WIN32
    if (state_->window != nullptr) {
        ShowWindow(state_->window, enabled ? SW_MAXIMIZE : SW_RESTORE);
    }
#else
    (void)enabled;
#endif
}