// This file was generated by SquareLine Studio
// SquareLine Studio version: SquareLine Studio 1.3.2
// LVGL version: 8.3.6
// Project name: SquareLine_Project

#include "../ui.h"

void ui_Screen3_screen_init(void)
{
ui_Screen3 = lv_obj_create(NULL);
lv_obj_clear_flag( ui_Screen3, LV_OBJ_FLAG_SCROLLABLE );    /// Flags

ui_Image5 = lv_img_create(ui_Screen3);
lv_img_set_src(ui_Image5, &ui_img_3_png);
lv_obj_set_width( ui_Image5, LV_SIZE_CONTENT);  /// 480
lv_obj_set_height( ui_Image5, LV_SIZE_CONTENT);   /// 320
lv_obj_set_align( ui_Image5, LV_ALIGN_CENTER );
lv_obj_add_flag( ui_Image5, LV_OBJ_FLAG_ADV_HITTEST );   /// Flags
lv_obj_clear_flag( ui_Image5, LV_OBJ_FLAG_SCROLLABLE );    /// Flags

ui_Button3 = lv_btn_create(ui_Screen3);
lv_obj_set_width( ui_Button3, 164);
lv_obj_set_height( ui_Button3, 57);
lv_obj_set_x( ui_Button3, -122 );
lv_obj_set_y( ui_Button3, -92 );
lv_obj_set_align( ui_Button3, LV_ALIGN_CENTER );
lv_obj_add_flag( ui_Button3, LV_OBJ_FLAG_SCROLL_ON_FOCUS );   /// Flags
lv_obj_clear_flag( ui_Button3, LV_OBJ_FLAG_SCROLLABLE );    /// Flags
lv_obj_set_style_bg_color(ui_Button3, lv_color_hex(0x39918B), LV_PART_MAIN | LV_STATE_DEFAULT );
lv_obj_set_style_bg_opa(ui_Button3, 255, LV_PART_MAIN| LV_STATE_DEFAULT);
lv_obj_set_style_shadow_color(ui_Button3, lv_color_hex(0x39918B), LV_PART_MAIN | LV_STATE_DEFAULT );
lv_obj_set_style_shadow_opa(ui_Button3, 255, LV_PART_MAIN| LV_STATE_DEFAULT);
lv_obj_set_style_shadow_width(ui_Button3, 5, LV_PART_MAIN| LV_STATE_DEFAULT);
lv_obj_set_style_shadow_spread(ui_Button3, 5, LV_PART_MAIN| LV_STATE_DEFAULT);

ui_Button4 = lv_btn_create(ui_Screen3);
lv_obj_set_width( ui_Button4, 164);
lv_obj_set_height( ui_Button4, 57);
lv_obj_set_x( ui_Button4, -122 );
lv_obj_set_y( ui_Button4, -8 );
lv_obj_set_align( ui_Button4, LV_ALIGN_CENTER );
lv_obj_add_flag( ui_Button4, LV_OBJ_FLAG_SCROLL_ON_FOCUS );   /// Flags
lv_obj_clear_flag( ui_Button4, LV_OBJ_FLAG_SCROLLABLE );    /// Flags
lv_obj_set_style_bg_color(ui_Button4, lv_color_hex(0xBD79AC), LV_PART_MAIN | LV_STATE_DEFAULT );
lv_obj_set_style_bg_opa(ui_Button4, 255, LV_PART_MAIN| LV_STATE_DEFAULT);
lv_obj_set_style_shadow_color(ui_Button4, lv_color_hex(0xBD79AC), LV_PART_MAIN | LV_STATE_DEFAULT );
lv_obj_set_style_shadow_opa(ui_Button4, 255, LV_PART_MAIN| LV_STATE_DEFAULT);
lv_obj_set_style_shadow_width(ui_Button4, 5, LV_PART_MAIN| LV_STATE_DEFAULT);
lv_obj_set_style_shadow_spread(ui_Button4, 5, LV_PART_MAIN| LV_STATE_DEFAULT);

ui_Button5 = lv_btn_create(ui_Screen3);
lv_obj_set_width( ui_Button5, 172);
lv_obj_set_height( ui_Button5, 80);
lv_obj_set_x( ui_Button5, -122 );
lv_obj_set_y( ui_Button5, 92 );
lv_obj_set_align( ui_Button5, LV_ALIGN_CENTER );
lv_obj_add_flag( ui_Button5, LV_OBJ_FLAG_SCROLL_ON_FOCUS );   /// Flags
lv_obj_clear_flag( ui_Button5, LV_OBJ_FLAG_SCROLLABLE );    /// Flags
lv_obj_set_style_bg_color(ui_Button5, lv_color_hex(0x27A39B), LV_PART_MAIN | LV_STATE_DEFAULT );
lv_obj_set_style_bg_opa(ui_Button5, 255, LV_PART_MAIN| LV_STATE_DEFAULT);
lv_obj_set_style_shadow_color(ui_Button5, lv_color_hex(0x20A19C), LV_PART_MAIN | LV_STATE_DEFAULT );
lv_obj_set_style_shadow_opa(ui_Button5, 255, LV_PART_MAIN| LV_STATE_DEFAULT);
lv_obj_set_style_shadow_width(ui_Button5, 5, LV_PART_MAIN| LV_STATE_DEFAULT);
lv_obj_set_style_shadow_spread(ui_Button5, 5, LV_PART_MAIN| LV_STATE_DEFAULT);

ui_Label3 = lv_label_create(ui_Screen3);
lv_obj_set_width( ui_Label3, LV_SIZE_CONTENT);  /// 1
lv_obj_set_height( ui_Label3, LV_SIZE_CONTENT);   /// 1
lv_obj_set_x( ui_Label3, -122 );
lv_obj_set_y( ui_Label3, -92 );
lv_obj_set_align( ui_Label3, LV_ALIGN_CENTER );
lv_label_set_text(ui_Label3,"Refresh");
lv_obj_set_style_text_color(ui_Label3, lv_color_hex(0xF8E1F4), LV_PART_MAIN | LV_STATE_DEFAULT );
lv_obj_set_style_text_opa(ui_Label3, 255, LV_PART_MAIN| LV_STATE_DEFAULT);
lv_obj_set_style_text_font(ui_Label3, &lv_font_montserrat_20, LV_PART_MAIN| LV_STATE_DEFAULT);

ui_Label4 = lv_label_create(ui_Screen3);
lv_obj_set_width( ui_Label4, LV_SIZE_CONTENT);  /// 1
lv_obj_set_height( ui_Label4, LV_SIZE_CONTENT);   /// 1
lv_obj_set_x( ui_Label4, -122 );
lv_obj_set_y( ui_Label4, -8 );
lv_obj_set_align( ui_Label4, LV_ALIGN_CENTER );
lv_label_set_text(ui_Label4,"Pause");
lv_obj_set_style_text_color(ui_Label4, lv_color_hex(0xF8E1F4), LV_PART_MAIN | LV_STATE_DEFAULT );
lv_obj_set_style_text_opa(ui_Label4, 255, LV_PART_MAIN| LV_STATE_DEFAULT);
lv_obj_set_style_text_font(ui_Label4, &lv_font_montserrat_20, LV_PART_MAIN| LV_STATE_DEFAULT);

ui_Label5 = lv_label_create(ui_Screen3);
lv_obj_set_width( ui_Label5, LV_SIZE_CONTENT);  /// 1
lv_obj_set_height( ui_Label5, LV_SIZE_CONTENT);   /// 1
lv_obj_set_x( ui_Label5, -122 );
lv_obj_set_y( ui_Label5, 92 );
lv_obj_set_align( ui_Label5, LV_ALIGN_CENTER );
lv_label_set_text(ui_Label5,"AutoPlay");
lv_obj_set_style_text_color(ui_Label5, lv_color_hex(0xF8E1F4), LV_PART_MAIN | LV_STATE_DEFAULT );
lv_obj_set_style_text_opa(ui_Label5, 255, LV_PART_MAIN| LV_STATE_DEFAULT);
lv_obj_set_style_text_font(ui_Label5, &lv_font_montserrat_20, LV_PART_MAIN| LV_STATE_DEFAULT);

ui_Roller1 = lv_roller_create(ui_Screen3);
lv_roller_set_options( ui_Roller1, "ILDA1\nILDA2\nILDA3\nILDA4\nILDA5\nILDA6\nILDA7\nILDA8\nILDA9\nILDA10", LV_ROLLER_MODE_NORMAL );
lv_obj_set_width( ui_Roller1, 170);
lv_obj_set_height( ui_Roller1, 190);
lv_obj_set_x( ui_Roller1, 114 );
lv_obj_set_y( ui_Roller1, -13 );
lv_obj_set_align( ui_Roller1, LV_ALIGN_CENTER );
lv_obj_set_style_text_color(ui_Roller1, lv_color_hex(0xFFE2F6), LV_PART_MAIN | LV_STATE_DEFAULT );
lv_obj_set_style_text_opa(ui_Roller1, 255, LV_PART_MAIN| LV_STATE_DEFAULT);
lv_obj_set_style_text_font(ui_Roller1, &lv_font_montserrat_16, LV_PART_MAIN| LV_STATE_DEFAULT);
lv_obj_set_style_bg_color(ui_Roller1, lv_color_hex(0xDFB3D4), LV_PART_MAIN | LV_STATE_DEFAULT );
lv_obj_set_style_bg_opa(ui_Roller1, 255, LV_PART_MAIN| LV_STATE_DEFAULT);
lv_obj_set_style_border_side(ui_Roller1, LV_BORDER_SIDE_NONE, LV_PART_MAIN| LV_STATE_DEFAULT);
lv_obj_set_style_shadow_color(ui_Roller1, lv_color_hex(0xDEB2D5), LV_PART_MAIN | LV_STATE_DEFAULT );
lv_obj_set_style_shadow_opa(ui_Roller1, 255, LV_PART_MAIN| LV_STATE_DEFAULT);
lv_obj_set_style_shadow_width(ui_Roller1, 16, LV_PART_MAIN| LV_STATE_DEFAULT);
lv_obj_set_style_shadow_spread(ui_Roller1, 16, LV_PART_MAIN| LV_STATE_DEFAULT);

lv_obj_set_style_bg_color(ui_Roller1, lv_color_hex(0x39918B), LV_PART_SELECTED | LV_STATE_DEFAULT );
lv_obj_set_style_bg_opa(ui_Roller1, 255, LV_PART_SELECTED| LV_STATE_DEFAULT);
lv_obj_set_style_shadow_color(ui_Roller1, lv_color_hex(0x39918B), LV_PART_SELECTED | LV_STATE_DEFAULT );
lv_obj_set_style_shadow_opa(ui_Roller1, 255, LV_PART_SELECTED| LV_STATE_DEFAULT);
lv_obj_set_style_shadow_width(ui_Roller1, 9, LV_PART_SELECTED| LV_STATE_DEFAULT);
lv_obj_set_style_shadow_spread(ui_Roller1, 9, LV_PART_SELECTED| LV_STATE_DEFAULT);

ui_Button6 = lv_btn_create(ui_Screen3);
lv_obj_set_width( ui_Button6, 176);
lv_obj_set_height( ui_Button6, 28);
lv_obj_set_x( ui_Button6, 144 );
lv_obj_set_y( ui_Button6, 138 );
lv_obj_set_align( ui_Button6, LV_ALIGN_CENTER );
lv_obj_add_flag( ui_Button6, LV_OBJ_FLAG_SCROLL_ON_FOCUS );   /// Flags
lv_obj_clear_flag( ui_Button6, LV_OBJ_FLAG_SCROLLABLE );    /// Flags
lv_obj_set_style_bg_color(ui_Button6, lv_color_hex(0xFFFFFF), LV_PART_MAIN | LV_STATE_DEFAULT );
lv_obj_set_style_bg_opa(ui_Button6, 0, LV_PART_MAIN| LV_STATE_DEFAULT);
lv_obj_set_style_shadow_color(ui_Button6, lv_color_hex(0x000000), LV_PART_MAIN | LV_STATE_DEFAULT );
lv_obj_set_style_shadow_opa(ui_Button6, 0, LV_PART_MAIN| LV_STATE_DEFAULT);

ui_Label6 = lv_label_create(ui_Screen3);
lv_obj_set_width( ui_Label6, LV_SIZE_CONTENT);  /// 1
lv_obj_set_height( ui_Label6, LV_SIZE_CONTENT);   /// 1
lv_obj_set_x( ui_Label6, 153 );
lv_obj_set_y( ui_Label6, 146 );
lv_obj_set_align( ui_Label6, LV_ALIGN_CENTER );
lv_label_set_text(ui_Label6,"Click here to return");
lv_obj_set_style_text_color(ui_Label6, lv_color_hex(0xFFFFFF), LV_PART_MAIN | LV_STATE_DEFAULT );
lv_obj_set_style_text_opa(ui_Label6, 255, LV_PART_MAIN| LV_STATE_DEFAULT);
lv_obj_set_style_text_font(ui_Label6, &lv_font_montserrat_14, LV_PART_MAIN| LV_STATE_DEFAULT);

lv_obj_add_event_cb(ui_Button3, ui_event_Button3, LV_EVENT_ALL, NULL);
lv_obj_add_event_cb(ui_Button4, ui_event_Button4, LV_EVENT_ALL, NULL);
lv_obj_add_event_cb(ui_Button5, ui_event_Button5, LV_EVENT_ALL, NULL);
lv_obj_add_event_cb(ui_Button6, ui_event_Button6, LV_EVENT_ALL, NULL);

}