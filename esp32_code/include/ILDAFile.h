#ifndef H_ILDAFILE_H
#define H_ILDAFILE_H

#include "main.h"

#include "FS.h"
#include <arpa/inet.h>
#include "esp32-hal-log.h"

typedef struct
{
    char ILDA[4];
    uint8_t reserved1[3];
    uint8_t format;
    char frame_name[8];
    char company_name[8];
    uint16_t records;
    uint16_t frame_number;
    uint16_t total_frames;
    uint8_t projector_number;
    uint8_t reserved2;
} ILDA_Header_t;

typedef struct
{
    int16_t x;
    int16_t y;
    int16_t z;
    uint8_t status_code;
    uint8_t color;
} ILDA_Record_t;

typedef struct
{
    ILDA_Record_t *records;
    uint16_t number_records;
    bool isBuffered = false;
} ILDA_Frame_t;

class ILDAFile
{
private:
    void dump_header(const ILDA_Header_t &header);

public:
    ILDAFile();
    ~ILDAFile();
    bool read(fs::FS &fs, const char *fname);
    bool tickNextFrame();
    bool parseStream(uint8_t *data, size_t len, int index, int totalLen);
    ILDA_Frame_t *frames;
    int file_frames;
    int cur_frame;
    int cur_buffer;
};

extern ILDAFile *ilda;

#endif /* H_ILDAFILE_H */