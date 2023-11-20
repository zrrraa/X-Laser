#include "ILDAFile.h"

ILDA_Header_t header;
File file;
unsigned long frameStart;

ILDAFile *ilda = new ILDAFile();
static const char *TAGILDA = "ILDA";

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
  dump_header(header);
  file_frames = header.total_frames;
  frameStart = file.position();
  return true;
}

// 缓存下一帧的内容
bool ILDAFile::tickNextFrame()
{
  // ESP_LOGI(TAGILDA, "tickNextFrame running on core %d", xPortGetCoreID());

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
      // 此处可以添加自动播放
      // if (digitalRead(4) == HIGH)
      // {
      //   nextMedia(1);
      // }
      // else
      nextMedia(0);
    }
    return true;
  }
  else
  {
    return false; // 该帧已缓存但是未投影，可能是读文件、串流太快了？忽视掉就好
  }
}