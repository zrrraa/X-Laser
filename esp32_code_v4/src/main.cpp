#include "main.h"

// 不用webstream功能时在这里定义
bool isStreaming = false;

static const char *TAGMAIN = "MAIN";

void setup()
{
  Serial.begin(115200);

  lcd_init();

  setupSD();

  // web_init();

  setupRenderer();

  //button_init();
}

void loop()
{
  //button_loop();
}