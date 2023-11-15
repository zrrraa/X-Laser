#include "main.h"

int kppsTime = 1000000 / (20 * 1000);
volatile unsigned long timeOld;
volatile unsigned long timeStart;

void setup()
{
  Serial.begin(115200);
  setupSD();
  web_init();
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