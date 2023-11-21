#include "main.h"

int kppsTime = 1000000 / (20 * 1000); // 20kHz

volatile unsigned long timeOld;
volatile unsigned long timeStart;

// 不用webstream功能时在这里定义
bool isStreaming = false;

static const char *TAGMAIN = "MAIN";

void setup()
{
  Serial.begin(115200);

  // digitalWrite(5, LOW);
  // digitalWrite(5, HIGH);
  // digitalWrite(5, HIGH);

  lcd_init();
  delay(2000);

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