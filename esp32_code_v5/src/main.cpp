#include "main.h"

// 考虑到硬件的散热能力，降低了频率
int kppsTime_media = 1000000 / (20 * 1000);
int kppsTime_draw = 1000000 / (3 * 1000);

volatile unsigned long timeOld;
volatile unsigned long timeStart;

// 不用webstream功能时在这里定义
bool isStreaming = false;

static const char *TAGMAIN = "MAIN";

void setup()
{
  Serial.begin(115200);

  // WRITE_PERI_REG(RTC_CNTL_BROWN_OUT_REG, 0); //关闭断电检测

  lcd_init();

  setupSD();

  // web_init();

  setupRenderer();
}

void loop()
{
  if (DrawNow_Flag == 0)
  {
    if (micros() - timeOld >= kppsTime_media)
    {
      timeOld = micros();
      draw_task();
    }
  }
  else if (DrawNow_Flag == 1)
  {
    if (micros() - timeOld >= kppsTime_draw)
    {
      timeOld = micros();
      draw_task();
    }
  }
}