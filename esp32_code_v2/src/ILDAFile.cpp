#include "ILDAFile.h"

ILDA_Header_t header;
File file;
unsigned long frameStart;

ILDAFile *ilda = new ILDAFile();
// ILDAFile *ilda;
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
  // Serial.println(file_frames);
  return true;
}

bool ILDAFile::tickNextFrame()
{
  //ESP_LOGI(TAGILDA, "tickNextFrame running on core %d", xPortGetCoreID());
  if (frames[cur_buffer].isBuffered == false)
  {
    // modify
    frames[cur_buffer].isBuffered = true;

    frames[cur_buffer].number_records = header.records;

    // frames[cur_buffer].records = (ILDA_Record_t *)malloc(sizeof(ILDA_Record_t) * header.records);

    ILDA_Record_t *records = frames[cur_buffer].records;
    for (int i = 0; i < header.records; i++)
    {
      file.read((uint8_t *)(records + i), sizeof(ILDA_Record_t));
      records[i].x = ntohs(records[i].x);
      records[i].y = ntohs(records[i].y);
      records[i].z = ntohs(records[i].z);
    }
    // read the next header
    file.read((uint8_t *)&header, sizeof(ILDA_Header_t));
    header.records = ntohs(header.records);
    header.total_frames = ntohs(header.total_frames);

    cur_buffer++;
    if (cur_buffer > bufferFrames - 1)
      cur_buffer = 0;

    cur_frame++;
    // Serial.println(cur_frame);
    if (cur_frame > file_frames - 1)
    {
      cur_frame = 0;
      // if (digitalRead(4) == HIGH)
      // { // 自动按钮，还未加
      //   nextMedia(1);
      // }
      // else
      nextMedia(0);
    }
    return true;
  }
  else
    return false; // This frame has been buffered and not display yet.. 该帧已缓存且未Render，可能是读文件、串流太快了？忽视掉就好
}