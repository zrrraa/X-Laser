#include "button.h"

Button2 buttonL, buttonR;

int buttonState = 0; // 让Core0 和 Core1的操作不要同时出现，不然就读着读着跳下一个文件就Crash了    无操作 -1   上一个 1  下一个 2  自动下一个 3  不要自动 4

void button_init()
{
    buttonL.begin(12, INPUT_PULLUP, false);
    buttonL.setTapHandler(click);

    buttonR.begin(22, INPUT_PULLUP, false);
    buttonR.setTapHandler(click);
}

void button_loop()
{
    buttonL.loop();
    buttonR.loop();
}
void click(Button2 &btn)
{
    if (btn == buttonL)
    {
        goPrev();
        Serial.println("buttonL clicked");
    }
    else if (btn == buttonR)
    {
        goNext();
        Serial.println("buttonR clicked");
    }
}

void goNext()
{
  buttonState = 2;
}

void goPrev()
{
  buttonState = 1;
}