#include "ILDAFile.h"

ILDA_Header_t header;
File file;
unsigned long frameStart;

ILDAFile *ilda = new ILDAFile();
static const char *TAGILDA = "ILDA";

// DrawNow模式下的一些定义
uint16_t DrawNow_records_position = 0;

ILDAFile::ILDAFile()
{
  frames = NULL;
  file_frames = 0;
  cur_frame = 0;
  cur_buffer = 0;
}

ILDAFile::~ILDAFile()
{
  free(frames);
}

// 打印ILDA文件header信息
void ILDAFile::dump_header(const ILDA_Header_t &header)
{
  char tmp[100];
  strncpy(tmp, header.ILDA, 4);
  tmp[5] = '\0';
  ESP_LOGI(TAGILDA, "Header: %s", tmp);
  ESP_LOGI(TAGILDA, "Format Code: %d", header.format);
  strncpy(tmp, header.frame_name, 8);
  tmp[8] = '\0';
  ESP_LOGI(TAGILDA, "Frame Name: %s", tmp);
  strncpy(tmp, header.company_name, 8);
  tmp[8] = '\0';
  ESP_LOGI(TAGILDA, "Company Name: %s", tmp);
  ESP_LOGI(TAGILDA, "Number records: %d", header.records);
  ESP_LOGI(TAGILDA, "Number frames: %d", header.total_frames);
}

// 读取ILDA文件header
bool ILDAFile::read(fs::FS &fs, const char *fname)
{
  file = fs.open(fname);
  if (!file)
  {
    return false;
  }
  file.read((uint8_t *)&header, sizeof(ILDA_Header_t));
  header.records = ntohs(header.records);
  header.total_frames = ntohs(header.total_frames);
  // dump_header(header);
  file_frames = header.total_frames;
  frameStart = file.position();
  return true;
}

// 缓存下一帧的内容
bool ILDAFile::tickNextFrame()
{
  // ESP_LOGI(TAGILDA, "tickNextFrame running on core %d", xPortGetCoreID());

  // 投影SD卡中的media模式
  if (DrawNow_Flag == 0)
  {
    // 这个buffer内未缓存过数据或者缓存的数据已经被投影出去了，可以缓存新的数据了
    if (frames[cur_buffer].isBuffered == false)
    {
      frames[cur_buffer].number_records = header.records;

      // frames[cur_buffer].records = (ILDA_Record_t *)malloc(sizeof(ILDA_Record_t) * header.records);

      // 缓存records并进行字节序转化
      ILDA_Record_t *records = frames[cur_buffer].records;
      for (int i = 0; i < header.records; i++)
      {
        file.read((uint8_t *)(records + i), sizeof(ILDA_Record_t));
        records[i].x = ntohs(records[i].x);
        records[i].y = ntohs(records[i].y);
        records[i].z = ntohs(records[i].z);
      }

      // 读取下一帧的header
      file.read((uint8_t *)&header, sizeof(ILDA_Header_t));
      header.records = ntohs(header.records);
      header.total_frames = ntohs(header.total_frames);

      frames[cur_buffer].isBuffered = true; // 缓存成功，把这一帧标记为buffered

      // 只设置了三帧的buffer，轮流缓存数据帧
      cur_buffer++;
      if (cur_buffer > bufferFrames - 1)
        cur_buffer = 0;

      // 此文件播放完毕，继续循环播放
      cur_frame++;
      if (cur_frame > file_frames - 1)
      {
        cur_frame = 0;
        // 自动播放
        if (AutoPlay_Flag == 1)
        {
          nextMedia(1);
        }
        else
          nextMedia(0);
      }
      return true;
    }
    else
    // 全部都缓存了
    {
      return false;
    }
  }
  // DrawNow模式，暂时只开发到一帧
  else
  {
    // ESP_LOGI(TAGILDA, "DrawNow mode, tick a record!");

    // 激光状态标记位，保证画迹断开后的第一个点不亮，防止曲线自动封闭
    // 25.03.28修改，每个独立路径的起始点和结束点都不亮，才能防止曲线封闭
    // ESP_LOGI(TAGILDA, "DrawNow mode, tick a record!, X_Position: %d, Y_Position: %d, X_Position_Old: %d, Y_Position_Old: %d", X_Position, Y_Position, X_Position_Old, Y_Position_Old);
    // 激光状态标记位处理
    if (abs(X_Position_Old - X_Position) > 20 || abs(Y_Position_Old - Y_Position) > 20)
    {
      // 新path开始
      printf("DrawNow_records_position: %d\n", DrawNow_records_position);
      // 处理旧路径结束点（非首条路径）
      if (DrawNow_records_position > 0)
      {
        int end_x = X_Position_Old;
        int end_y = Y_Position_Old;
        for (int i = 0; i < 10; i++)
        {
          ilda->frames[0].records[DrawNow_records_position].status_code = 0b01000000; // 不亮状态
          ilda->frames[0].records[DrawNow_records_position].color = 0;                // 颜色置零
          ilda->frames[0].records[DrawNow_records_position].x = end_x;
          ilda->frames[0].records[DrawNow_records_position].y = end_y;
          DrawNow_records_position++;
          ilda->frames[0].number_records++;
        }
      }

      // 处理新路径起始点（包含首条路径）
      int start_x = X_Position;
      int start_y = Y_Position;
      for (int i = 0; i < 10; i++)
      {
        ilda->frames[0].records[DrawNow_records_position].status_code = 0b01000000; // 不亮状态
        ilda->frames[0].records[DrawNow_records_position].color = 0;                // 颜色置零
        ilda->frames[0].records[DrawNow_records_position].x = start_x;
        ilda->frames[0].records[DrawNow_records_position].y = start_y;
        DrawNow_records_position++;
        ilda->frames[0].number_records++;
      }

      // 当前点设为正常状态
      ilda->frames[0].records[DrawNow_records_position].status_code = 0b00000000;

      // 颜色处理逻辑
      ilda->frames[0].records[DrawNow_records_position].color = 0;
      lv_color_t color = lv_colorwheel_get_rgb(ui_Colorwheel1);
      if (LV_COLOR_GET_R(color) > 15)
        ilda->frames[0].records[DrawNow_records_position].color |= 0b11100000; // 红色通道
      if (LV_COLOR_GET_G(color) > 31)
        ilda->frames[0].records[DrawNow_records_position].color |= 0b00011000; // 绿色通道
      if (LV_COLOR_GET_B(color) > 15)
        ilda->frames[0].records[DrawNow_records_position].color |= 0b00000111; // 蓝色通道

      // 坐标更新与记录
      ilda->frames[0].records[DrawNow_records_position].x = X_Position;
      ilda->frames[0].records[DrawNow_records_position].y = Y_Position;
      X_Position_Old = X_Position;
      Y_Position_Old = Y_Position;
      DrawNow_records_position++;
      ilda->frames[0].number_records++;
    }
    else
    {
      // 在一条path中
      int current_pos = DrawNow_records_position;
      ilda->frames[0].records[DrawNow_records_position].status_code = 0b00000000;
      // 追加10个不亮点
      for (int i = 0; i < 10; i++)
      {
        int blank_pos = current_pos + 1 + i;
        ilda->frames[0].records[blank_pos].status_code = 0b01000000; // 不亮状态
        ilda->frames[0].records[blank_pos].color = 0;                // 颜色置零
        ilda->frames[0].records[blank_pos].x = X_Position;
        ilda->frames[0].records[blank_pos].y = Y_Position;
      }

      // 颜色处理逻辑
      ilda->frames[0].records[DrawNow_records_position].color = 0;
      lv_color_t color = lv_colorwheel_get_rgb(ui_Colorwheel1);
      if (LV_COLOR_GET_R(color) > 15)
        ilda->frames[0].records[DrawNow_records_position].color |= 0b11100000; // 红色通道
      if (LV_COLOR_GET_G(color) > 31)
        ilda->frames[0].records[DrawNow_records_position].color |= 0b00011000; // 绿色通道
      if (LV_COLOR_GET_B(color) > 15)
        ilda->frames[0].records[DrawNow_records_position].color |= 0b00000111; // 蓝色通道

      // 坐标更新与记录
      ilda->frames[0].records[DrawNow_records_position].x = X_Position;
      ilda->frames[0].records[DrawNow_records_position].y = Y_Position;
      X_Position_Old = X_Position;
      Y_Position_Old = Y_Position;

      // 更新记录指针
      DrawNow_records_position = current_pos + 1;        // 返回最后一个非空白点
      ilda->frames[0].number_records = current_pos + 11; // 总记录数包含10个空白点
    }

    return false; // 存完这个点就让fileBufferLoop阻塞
  }
}