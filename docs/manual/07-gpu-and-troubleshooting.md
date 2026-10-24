# 7. GPU and troubleshooting

## NVIDIA GPUs

Start Pipelab with `make up GPU=1`. This needs the NVIDIA driver and the NVIDIA Container
Toolkit on the host. Every element of `nvcodec` is then available:

- NVDEC decoders: `nvh264dec`, `nvh265dec`, `nvvp9dec`, `nvjpegdec`…
- NVENC encoders: `nvh264enc`, `nvh265enc`, `nvautogpuh264enc`…
- memory transfer: `cudaupload` and `cudadownload`;
- CUDA filters that keep frames on the GPU: `cudaconvertscale`, `cudaconvert`, `cudascale` and
  `cudacompositor`.

Elements are registered according to the card. For example, AV1 (`nvav1enc`, `nvav1dec`) only
appears on GPUs that support it in hardware. Hardware limits are part of each element's caps:
`nvh264dec` decodes H.264 up to 4096 pixels wide, while `nvh265dec` handles H.265 up to 8192.

The validator understands GPU memory. Linking an element that outputs
`video/x-raw(memory:CUDAMemory)` to one that only accepts system memory suggests `cudadownload`.

## Common problems

**The pipeline stays in PAUSED, or one branch never receives data.**
A `tee` or demuxer branch has no `queue`, and a sink waiting for its first buffer (preroll)
blocks the others. Apply the *Insert queues* fix from the Issues tab.

**not-negotiated.**
Two elements could not agree on caps at runtime. The bus message names the link and the field
that does not match (for example `width` beyond a decoder's maximum). Add a converter or scaler,
or change the capsfilter.

**A decoder fails with a large camera stream.**
The resolution may be beyond the hardware decoder's limit: H.264 above 4096 px with `nvh264dec`.
Decode on the CPU (`avdec_h264`), or ask the camera for a smaller stream or for H.265.

**A preview looks slow.**
Previews are limited to about 15 frames per second to save bandwidth. The real rate of each link
is in the Stats tab and on the links themselves.

**A queue is always full.**
Whatever comes after it is too slow. See the Performance tab for the element and the thread
involved.

**RTP sender and receiver in the same pipeline never start.**
Set `async=false` on the sink. The validator warns about this case.
