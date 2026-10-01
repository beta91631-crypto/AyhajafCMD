#include "stream.hpp"

#include <cctype>
#include <cmath>
#include <cstdlib>
#include <fstream>
#include <iterator>

namespace {
void appendUtf8(std::string& output, unsigned int codepoint) {
    if (codepoint <= 0x7f) {
        output.push_back(static_cast<char>(codepoint));
    } else if (codepoint <= 0x7ff) {
        output.push_back(static_cast<char>(0xc0 | (codepoint >> 6)));
        output.push_back(static_cast<char>(0x80 | (codepoint & 0x3f)));
    } else if (codepoint <= 0xffff) {
        output.push_back(static_cast<char>(0xe0 | (codepoint >> 12)));
        output.push_back(static_cast<char>(0x80 | ((codepoint >> 6) & 0x3f)));
        output.push_back(static_cast<char>(0x80 | (codepoint & 0x3f)));
    } else {
        output.push_back(static_cast<char>(0xf0 | (codepoint >> 18)));
        output.push_back(static_cast<char>(0x80 | ((codepoint >> 12) & 0x3f)));
        output.push_back(static_cast<char>(0x80 | ((codepoint >> 6) & 0x3f)));
        output.push_back(static_cast<char>(0x80 | (codepoint & 0x3f)));
    }
}

class JsonObjectReader {
public:
    explicit JsonObjectReader(const std::string& source) : source_(source) {}

    bool read(StreamInfo& stream) {
        skipWhitespace();
        if (!consume('{')) return false;
        skipWhitespace();
        bool closed = false;
        while (!atEnd() && source_[position_] != '}') {
            std::string key;
            if (!readString(key)) return false;
            skipWhitespace();
            if (!consume(':')) return false;
            skipWhitespace();
            if (key == "video_url" || key == "audio_url" || key == "title") {
                std::string value;
                if (!readString(value)) return false;
                if (key == "video_url") stream.videoUrl = std::move(value);
                else if (key == "audio_url") stream.audioUrl = std::move(value);
                else stream.title = std::move(value);
            } else if (key == "duration" || key == "fps" || key == "width" || key == "height") {
                if (source_.compare(position_, 4, "null") == 0) {
                    position_ += 4;
                } else {
                    char* end = nullptr;
                    const double value = std::strtod(source_.c_str() + position_, &end);
                    if (end == source_.c_str() + position_ || !std::isfinite(value)) return false;
                    position_ = static_cast<size_t>(end - source_.c_str());
                    if (key == "duration") {
                        if (value < 0.0) return false;
                        stream.duration = value;
                        stream.hasDuration = true;
                    } else if (key == "fps") {
                        if (value <= 0.0) return false;
                        stream.fps = value;
                    } else if (key == "width" || key == "height") {
                        if (value < 1.0 || value > 10000.0 || std::floor(value) != value) return false;
                        if (key == "width") stream.width = static_cast<int>(value);
                        else stream.height = static_cast<int>(value);
                    }
                }
            } else if (!skipValue()) {
                return false;
            }
            skipWhitespace();
            if (consume('}')) {
                closed = true;
                break;
            }
            if (!consume(',')) return false;
            skipWhitespace();
        }
        skipWhitespace();
        if (!closed) closed = consume('}');
        return closed && atEnd() && !stream.videoUrl.empty() &&
               !stream.audioUrl.empty() && stream.width > 0 && stream.height > 0;
    }

private:
    bool atEnd() const { return position_ >= source_.size(); }

    void skipWhitespace() {
        while (!atEnd() && std::isspace(static_cast<unsigned char>(source_[position_]))) {
            ++position_;
        }
    }

    bool consume(char expected) {
        if (atEnd() || source_[position_] != expected) return false;
        ++position_;
        return true;
    }

    bool readHex(unsigned int& value) {
        if (position_ + 4 > source_.size()) return false;
        value = 0;
        for (int index = 0; index < 4; ++index) {
            const char digit = source_[position_++];
            value <<= 4;
            if (digit >= '0' && digit <= '9') value |= static_cast<unsigned int>(digit - '0');
            else if (digit >= 'a' && digit <= 'f') value |= static_cast<unsigned int>(digit - 'a' + 10);
            else if (digit >= 'A' && digit <= 'F') value |= static_cast<unsigned int>(digit - 'A' + 10);
            else return false;
        }
        return true;
    }

    bool readString(std::string& output) {
        if (!consume('"')) return false;
        while (!atEnd()) {
            const unsigned char value = static_cast<unsigned char>(source_[position_++]);
            if (value == '"') return true;
            if (value < 0x20) return false;
            if (value != '\\') {
                output.push_back(static_cast<char>(value));
                continue;
            }
            if (atEnd()) return false;
            const char escape = source_[position_++];
            switch (escape) {
                case '"': output.push_back('"'); break;
                case '\\': output.push_back('\\'); break;
                case '/': output.push_back('/'); break;
                case 'b': output.push_back('\b'); break;
                case 'f': output.push_back('\f'); break;
                case 'n': output.push_back('\n'); break;
                case 'r': output.push_back('\r'); break;
                case 't': output.push_back('\t'); break;
                case 'u': {
                    unsigned int codepoint = 0;
                    if (!readHex(codepoint)) return false;
                    if (codepoint >= 0xd800 && codepoint <= 0xdbff) {
                        if (position_ + 2 > source_.size() || source_[position_] != '\\' ||
                            source_[position_ + 1] != 'u') return false;
                        position_ += 2;
                        unsigned int low = 0;
                        if (!readHex(low) || low < 0xdc00 || low > 0xdfff) return false;
                        codepoint = 0x10000 + ((codepoint - 0xd800) << 10) + (low - 0xdc00);
                    } else if (codepoint >= 0xdc00 && codepoint <= 0xdfff) {
                        return false;
                    }
                    appendUtf8(output, codepoint);
                    break;
                }
                default: return false;
            }
        }
        return false;
    }

    bool skipValue() {
        if (atEnd()) return false;
        if (source_[position_] == '"') {
            std::string ignored;
            return readString(ignored);
        }
        while (!atEnd() && source_[position_] != ',' && source_[position_] != '}' &&
               !std::isspace(static_cast<unsigned char>(source_[position_]))) {
            ++position_;
        }
        return true;
    }

    const std::string& source_;
    size_t position_ = 0;
};
}

bool loadStreamInfo(const std::string& path, StreamInfo& stream, std::string& error) {
    std::ifstream file(path, std::ios::binary);
    if (!file) {
        error = "Could not open stream metadata.";
        return false;
    }
    const std::string contents((std::istreambuf_iterator<char>(file)),
                               std::istreambuf_iterator<char>());
    if (contents.size() > 4U * 1024U * 1024U ||
        !JsonObjectReader(contents).read(stream) || !(stream.fps > 0.0)) {
        error = "Stream metadata is invalid or incomplete.";
        return false;
    }
    if (stream.title.empty()) stream.title = "YouTube video";
    stream.fps = stream.fps > 30.0 ? 30.0 : stream.fps;
    return true;
}