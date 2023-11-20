#include "main.h"

// int kppsTime = 1000000 / (20 * 1000);
int kppsTime = 50;
volatile unsigned long timeOld;
volatile unsigned long timeStart;

// 不用webstream功能时在这里定义
bool isStreaming = false;

static const char *TAGMAIN = "MAIN";

void setup()
{
  Serial.begin(115200);

  setupSD();

  // web_init();

  lcd_init();

  setupRenderer();
  button_init();
}

void loop()
{
  if (micros() - timeOld >= kppsTime)
  {
    timeOld = micros();
    draw_task();
  }
  button_loop();
}