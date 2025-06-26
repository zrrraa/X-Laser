#include "main.h"

// drawNow模式下，振镜频率随着画的点数增多而增加，不会在点数较少时由于频率过高导致电流过大
int kppsTime_media = 1000000 / (40 * 1000);
int kppsTime_draw = 1000000 / (1 * 1000);

volatile unsigned long timeOld;
volatile unsigned long timeStart;

static const char *TAGMAIN = "MAIN";

// 0: PC 1: TFTLCD
int file_mode = 1;

void setup()
{
  // 交互方式选择
  pinMode(PIN_NUM_FILEMODE, INPUT);
  file_mode = digitalRead(PIN_NUM_FILEMODE);

  Serial.begin(921600);
  
  if (file_mode)
  {
    lcd_init();

    setupSD();
  }
  else
  {
    setupFilePush();
  }
  
  setupRenderer();
}

void loop()
{
  if(file_mode == 0) // PC模式轮询串口状态
  {
    loopFilePush();
  }

  if (DrawNow_Flag == 0)
  {
    if (micros() - timeOld >= kppsTime_media)
    {
      timeOld = micros();
      draw_task();
    }
  }
  else if (DrawNow_Flag == 1 && ilda->frames[0].number_records > 0)
  {
    // 调控振镜频率
    kppsTime_draw = 1000000 / (1 * 1000) * (ilda->frames[0].number_records / 2 + 1);
    if (kppsTime_draw > 1000000 / (25 * 1000))
    {
      kppsTime_draw = 1000000 / (25 * 1000);
    }

    if (micros() - timeOld >= kppsTime_draw)
    {
      timeOld = micros();
      draw_task();
    }
  }
}