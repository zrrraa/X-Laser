#include "main.h"

// int kppsTime = 1000000 / (20 * 1000);
int kppsTime = 50;
volatile unsigned long timeOld;
volatile unsigned long timeStart;

// TaskHandle_t drawing;

void setup()
{
  Serial.begin(115200);
  setupSD();
  // web_init();
  setupRenderer();
  button_init();
  // xTaskCreatePinnedToCore(Draw_Task, "drawing", 8192, NULL, 1, &drawing, 1);
  //  Serial.println("Draw_Task create on Core 1");
  //  delay(1000);
}

void loop()
{
  if (micros() - timeOld >= kppsTime)
  {
    timeOld = micros();
    draw_task();
  }
  button_loop();
  // Serial.print("main_loop running on core ");
  // Serial.println(xPortGetCoreID());
}