#include "main.h"

int kppsTime = 1000000 / (40 * 1000); // 实际会慢于40kHz
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

  // button_init();
}

void loop()
{
  if (micros() - timeOld >= kppsTime)
  {
    timeOld = micros();
    draw_task();
  }
  // button_loop();
}