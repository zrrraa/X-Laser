SET(SOURCES screens/ui_Screen1.c
    screens/ui_Screen2.c
    screens/ui_Screen3.c
    screens/ui_Screen4.c
    ui.c
    components/ui_comp_hook.c
    ui_helpers.c
    ui_events.c
    images/ui_img_1_png.c
    images/ui_img_2_png.c
    images/ui_img_3_png.c)

add_library(ui ${SOURCES})
