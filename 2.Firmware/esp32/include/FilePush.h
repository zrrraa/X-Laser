#ifndef H_FILEPUSH_H
#define H_FILEPUSH_H

#include "main.h"

#include <FS.h>
#include "SD_MMC.h"

#define FILE_BUFFER_SIZE 1024

void setupFilePush();
void loopFilePush();
void clearFilePushFolder();
void RenderPushFile();

extern bool filePushDrawFlag;

#endif