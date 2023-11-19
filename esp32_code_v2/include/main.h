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
#include "Webstream.h"
#include "MyTFTLCD.h"

void Task1code(void *pvParameters);

#endif /* H_MAIN_H */