#ifndef H_MAIN_H
#define H_MAIN_H

#include <string>
#include <cstring>
#include <stdint.h>
#include <Arduino.h>

#include "button.h"
#include "SDCard.h"
#include "SPIRenderer.h"
#include "ILDAFile.h"
#include "CoreLoop.h"
// #include "Webstream.h"
#include "MyTFTLCD.h"

// 不用webstream功能时注释掉定义，并修改相关的isStream定义和声明
// #define USE_WEB_STREAM
extern bool isStreaming;

#endif /* H_MAIN_H */