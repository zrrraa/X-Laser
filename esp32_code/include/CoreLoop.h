#ifndef H_CORELOOP_H
#define H_CORELOOP_H

#include "main.h"

#include "soc/timer_group_struct.h"
#include "soc/timer_group_reg.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"

extern bool isStreaming;

void fileBufferLoop(void *pvParameters);

#endif /* H_CORELOOP_H */