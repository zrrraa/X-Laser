#ifndef H_BUTTON_H
#define H_BUTTON_H

#include "main.h"

#include "Button2.h"

extern int buttonState;

void button_init();
void button_loop();
void click(Button2 &btn);
void goNext();
void goPrev();

#endif /* H_BUTTON_H */