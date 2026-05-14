#ifndef H_MAIN_H
#define H_MAIN_H

#include <string>
#include <cstring>
#include <stdint.h>
#include <math.h>
#include <Arduino.h>
#include "soc/soc.h"
#include "soc/rtc_cntl_reg.h"

#include "SDCard.h"
#include "SPIRenderer.h"
#include "ILDAFile.h"
#include "CoreLoop.h"
#include "MyTFTLCD.h"
#include "FilePush.h"

#define PIN_NUM_FILEMODE 35

extern int file_mode;

#endif /* H_MAIN_H */