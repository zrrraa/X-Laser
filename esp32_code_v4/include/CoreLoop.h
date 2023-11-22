#ifndef H_CORELOOP_H
#define H_CORELOOP_H

#include "main.h"

#include "soc/timer_group_struct.h"
#include "soc/timer_group_reg.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

void fileBufferLoop(void *pvParameters);
void myTFTLCDLoop(void *pvParameters);
void drawTaskLoop(void *pvParameters);

extern int TFTLCD_BUTTON;

#endif /* H_CORELOOP_H */