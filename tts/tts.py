import base64
import edge_tts
import asyncio
import os
import pilk
import av
OUTPUT_FILE_DIR = os.path.join(os.path.dirname(__file__), "audio.mp3")
async def generate_audio(text):
    communcate = edge_tts.Communicate(text, "zh-CN-XiaoxiaoNeural")
    await communcate.save(OUTPUT_FILE_DIR)
def to_pcm(in_path: str) -> tuple[str, int]:
    """任意媒体文件转 pcm"""
    out_path = os.path.splitext(in_path)[0] + '.pcm'
    with av.open(in_path) as in_container:
        in_stream = in_container.streams.audio[0]
        sample_rate = in_stream.codec_context.sample_rate
        with av.open(out_path, 'w', 's16le') as out_container:
            out_stream = out_container.add_stream(
                'pcm_s16le',
                rate=sample_rate,
                layout='mono'
            )
            try:
               for frame in in_container.decode(in_stream):
                  frame.pts = None
                  for packet in out_stream.encode(frame):
                     out_container.mux(packet)
            except:
               pass
    return out_path, sample_rate
async def tts(text):
    await generate_audio(text)
    pcm_path,sample_rate = to_pcm(OUTPUT_FILE_DIR)
    silk_path = os.path.splitext(pcm_path)[0] + '.silk'
    pilk.encode(pcm_path, silk_path, pcm_rate=sample_rate, tencent=True)
    return silk_path

async def return_tts_base64data(text):
    if len(text) < 160:
        silk_voice_path = await tts(text)
    else:
        silk_voice_path = await tts('文本内容过长')
    with open(silk_voice_path, "rb") as silk_voice:
        return base64.b64encode(silk_voice.read()).decode('utf-8')

if __name__ == "__main__":
    asyncio.run(tts('测试'))