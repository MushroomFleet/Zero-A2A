# Seedance Video Generator & Post-Processing Platform

A comprehensive video generation and post-processing platform that combines ByteDance's Seedance AI model with advanced video effects. Generate high-quality videos from images and text prompts, then enhance them with retro post-processing effects including cathode ray tube (CRT) styling.

## Features

### Video Generation
- **Image-to-Video Generation**: Generate 5-10 second videos from uploaded images with descriptive text prompts
- **Multiple Quality Options**: Support for 480p and 720p resolutions
- **Camera Control**: Fixed camera position option for less motion
- **Image Processing**: Automatic image optimization and base64 conversion
- **Cost Effective**: Uses Seedance 1.0 Lite model at $0.18 per 5-second video

### Queue Management System
- **Real-time Queue Tracking**: Live updates of generation progress
- **Position Tracking**: See your place in the processing queue
- **Queue Statistics**: View pending, processing, completed, and failed requests
- **Estimated Wait Times**: Get time estimates for pending requests
- **Auto-refresh**: Automatic queue status updates
- **Queue Control**: Remove pending requests from queue

### Post-Processing Effects
- **Cathode Ray Effect**: Retro CRT monitor styling with configurable parameters
- **Screen Curvature**: Simulate vintage monitor screen curvature
- **Scanlines**: Add authentic CRT scanline effects
- **Glow Effects**: Screen glow and phosphor persistence simulation
- **Color Bleeding**: RGB color separation effects
- **Dynamic Noise**: Film grain and signal interference
- **Effect Presets**: Static, fluctuating, degraded, and custom timing modes

### Video Management
- **Local Storage**: Videos automatically saved to `./public/videos/` directory
- **Gallery Management**: Browse, preview, download, and delete generated videos
- **Effect History**: Track applied effects for each video
- **Metadata Management**: Comprehensive video metadata with generation parameters
- **Progress Tracking**: Real-time generation and processing progress

## Technology Stack

### Frontend
- **Next.js 15.3.5**: React framework with server-side rendering
- **React 18**: Component library with hooks
- **TypeScript**: Type-safe development
- **Tailwind CSS**: Utility-first CSS framework
- **Zustand**: Lightweight state management

### Backend & APIs
- **FAL.ai Client**: Integration with Seedance AI model
- **Server-side Proxy**: Secure API key handling
- **Node.js APIs**: RESTful endpoints for video and queue management

### Video Processing
- **Python 3**: Video effect processing engine
- **OpenCV**: Computer vision and video manipulation
- **NumPy**: Numerical computing for effect algorithms

### Storage
- **Local File System**: Video file storage
- **JSON Metadata**: Video metadata and queue state management

## Prerequisites

- Node.js 18+ 
- npm or yarn
- Python 3.7+ with pip
- **FFmpeg** (required for video post-processing)
- FAL.ai API key

### System Dependencies

#### FFmpeg Installation
FFmpeg is required for video post-processing optimization:

**Windows:**
- Download from [https://ffmpeg.org/download.html](https://ffmpeg.org/download.html)
- Add to system PATH

**macOS:**
```bash
brew install ffmpeg
```

**Linux (Ubuntu/Debian):**
```bash
sudo apt-get update
sudo apt-get install ffmpeg
```

#### Python Dependencies
Install required Python packages:
```bash
pip install opencv-python numpy
```

### Dependency Verification
Verify all dependencies are properly installed:
```bash
# Check FFmpeg
ffmpeg -version

# Check Python packages
python -c "import cv2, numpy; print('OpenCV and NumPy installed successfully')"
```

## Installation

1. Clone or download this repository
2. Install Node.js dependencies:
   ```bash
   npm install
   ```

3. Install Python dependencies:
   ```bash
   pip install opencv-python numpy
   ```

4. Set up environment variables:
   ```bash
   cp env.example .env.local
   ```

5. Add your FAL.ai API key to `.env.local`:
   ```
   FAL_KEY_SECRET=your_fal_api_key_here
   ```

6. Start the development server:
   ```bash
   npm run dev
   ```

7. Open [http://localhost:3000](http://localhost:3000) in your browser

## Getting FAL.ai API Key

1. Visit [https://fal.ai/](https://fal.ai/)
2. Sign up for an account
3. Navigate to your dashboard
4. Generate an API key
5. Copy the key to your `.env.local` file

## Usage

### Generating Videos

1. **Upload an image**: Click to upload a PNG, JPG, or WEBP image (up to 10MB)
2. **Enter a descriptive prompt**: Describe how you want the image to move and animate
3. **Adjust settings**:
   - **Duration**: 5s ($0.18) or 10s ($0.36)
   - **Resolution**: 480p or 720p
   - **Camera Fixed**: Enable for less camera movement (more stable)
4. Click "Generate Video"
5. Video is added to the generation queue
6. Monitor progress in the queue display
7. Completed videos are automatically saved to `./public/videos/`

### Queue Management

- **View Queue Status**: Real-time display shows all requests and their status
- **Monitor Progress**: Watch generation progress with live updates
- **Queue Position**: See your position in the processing queue
- **Estimated Times**: Get time estimates for pending requests
- **Remove Requests**: Cancel pending requests before processing starts
- **Auto-refresh**: Enable automatic queue updates (enabled by default)

### Applying Post-Processing Effects

1. **Open Gallery**: Click "View Gallery" to browse existing videos
2. **Select Video**: Choose a video for post-processing
3. **Apply Effects**: Click the effect button on a video thumbnail
4. **Configure Effect**: Choose from preset configurations:
   - **Static**: Consistent effect throughout
   - **Fluctuating**: Subtle variations over time
   - **Degraded**: Progressive signal degradation
   - **Custom**: Define custom timing expressions
5. **Start Processing**: Apply the cathode ray effect
6. **Monitor Progress**: Watch processing progress
7. **View Result**: Processed video is saved with effect suffix

### Managing Videos

- **Gallery View**: Browse all generated and processed videos
- **Video Preview**: Click on videos to preview them
- **Download**: Download videos directly from the gallery
- **Delete**: Remove unwanted videos
- **Metadata**: View generation parameters and applied effects
- **Effect History**: See which effects have been applied to each video

## File Structure

```
/seedance-api/
├── src/
│   ├── app/
│   │   ├── api/
│   │   │   ├── fal/proxy/             # FAL.ai API proxy
│   │   │   ├── videos/save/           # Video storage API
│   │   │   ├── queue/                 # Queue management APIs
│   │   │   └── postfx/                # Post-processing APIs
│   │   ├── layout.tsx                 # App layout
│   │   ├── page.tsx                   # Main page
│   │   └── globals.css                # Global styles
│   ├── components/
│   │   ├── VideoGenerationForm.tsx    # Video generation form
│   │   ├── GalleryModal.tsx           # Video gallery modal
│   │   ├── QueueDisplay.tsx           # Real-time queue display
│   │   ├── PostFXModal.tsx            # Post-processing interface
│   │   └── ToastNotification.tsx      # User notifications
│   ├── lib/
│   │   ├── fal-client.ts              # FAL.ai client with retry logic
│   │   ├── file-manager.ts            # Video file management
│   │   ├── queue-store.ts             # Queue state management
│   │   ├── queue-manager.ts           # Queue processing logic
│   │   └── notification-store.ts      # Notification system
│   └── types/
│       ├── video.ts                   # Video and effect types
│       └── queue.ts                   # Queue management types
├── scripts/
│   └── cathode_ray_processor.py       # Enhanced video effect processor with FFmpeg
├── docs/
│   ├── SEEDANCE-DEVTEAM-HANDOFF.md    # Technical specification
│   ├── postfx-output-format.md        # PostFX development standards
│   └── API_RESPONSE_LOGGING.md        # API logging documentation
├── public/
│   ├── videos/                        # Generated and processed videos
│   ├── logs/                          # API response logs
│   └── metadata.json                  # Video metadata storage
├── package.json
├── next.config.js
├── tailwind.config.js
└── README.md
```

## Configuration

### Environment Variables

- `FAL_KEY_SECRET`: Your FAL.ai API key (required)
- `NODE_ENV`: Set to 'development' for detailed error messages

### Video Generation Settings

- **Model**: Uses `fal-ai/bytedance/seedance/v1/lite/image-to-video`
- **Cost**: $0.18 per 5-second 720p video, $0.36 per 10-second video
- **Formats**: MP4 with H.264 encoding
- **Frame Rate**: 24 FPS

### Enhanced Video Processing Pipeline

The platform includes a robust video processing pipeline with multiple reliability improvements:

#### Video Generation
- **H.264 Encoding**: All videos generated with web-compatible H.264 format
- **Automatic Quality Control**: Validation of generated video files
- **Retry Logic**: Automatic retry for failed generation attempts
- **Progress Tracking**: Real-time generation progress updates

#### Post-Processing Pipeline
- **Multi-Codec Fallback**: H.264 → MJPG → XVID → mp4v codec prioritization
- **FFmpeg Optimization**: Automatic re-encoding for web compatibility
- **Video Validation**: Integrity checking before completion
- **Error Recovery**: Comprehensive error handling and cleanup

#### Thumbnail Generation
- **Enhanced Error Handling**: Detailed error categorization and logging
- **Automatic Retry**: Smart retry logic for transient failures
- **CORS Support**: Proper cross-origin handling for video streaming
- **Caching**: Intelligent caching with failure tracking

### Post-Processing Effect Parameters

#### Cathode Ray Effect
- **Screen Curvature** (0.0-1.0): Simulates vintage monitor curvature
- **Scanline Intensity** (0.0-1.0): Strength of horizontal scanlines
- **Glow Amount** (0.0-1.0): Screen phosphor glow effect
- **Color Bleeding** (0.0-1.0): RGB color separation
- **Noise Amount** (0.0-1.0): Signal interference and grain
- **Presets**: 
  - Static: Consistent effect
  - Fluctuating: `0.8 + 0.2 * sin(t / 5)`
  - Degraded: `max(0.5, 1.0 - t / (total_frames * 2))`
  - Custom: User-defined expressions with `t` (time) variable

## Local Storage

### Generated Videos
- **Location**: `./public/videos/`
- **Format**: MP4 files with descriptive filenames
- **Naming**: `{description}_{timestamp}_{resolution}_{duration}.mp4`

### Processed Videos
- **Location**: `./public/videos/`
- **Format**: Original filename + effect suffix
- **Naming**: `{original}_cathode-ray_{timestamp}.mp4`

### Metadata
- **Location**: `./public/metadata.json`
- **Content**: Video information, generation parameters, effect history
- **Structure**: Array of VideoMetadata objects with comprehensive details

## API Endpoints

### Video Generation
- `POST /api/fal/proxy` - Generate video via FAL.ai
- `POST /api/videos/save` - Save generated video

### Queue Management
- `GET /api/queue` - Get queue status
- `POST /api/queue` - Add request to queue
- `DELETE /api/queue/[id]` - Remove request from queue

### Post-Processing
- `POST /api/postfx/process` - Start effect processing
- `GET /api/postfx/status/[jobId]` - Get processing status

## Troubleshooting

### Common Issues

1. **"Module not found" errors**: Run `npm install` to ensure all dependencies are installed
2. **Python not found**: Ensure Python 3.7+ is installed and in PATH
3. **FFmpeg not found**: Ensure FFmpeg is installed and available in system PATH
4. **OpenCV errors**: Install OpenCV with `pip install opencv-python`
5. **API errors**: Check that your FAL_KEY_SECRET is correct in `.env.local`
6. **Videos not saving**: Ensure the application has write permissions to the project directory
7. **Generation fails**: Check console logs for detailed error messages
8. **Queue not updating**: Verify auto-refresh is enabled and network connectivity
9. **Post-processing fails**: Check Python installation, OpenCV dependencies, and FFmpeg availability
10. **Thumbnail generation errors**: Check browser console for detailed video loading error information
11. **Video format compatibility**: Processed videos should automatically be optimized for web playback

### Error Messages

#### Video Generation
- **"Upload Image First"**: You must upload an image before generating a video
- **"Add Description"**: Enter a text description of how the image should animate
- **"Failed to download video"**: Network issue or FAL.ai service unavailable
- **"Image file size must be less than 10MB"**: Choose a smaller image file
- **"Please select a valid image file"**: Only PNG, JPG, and WEBP formats are supported

#### Queue Management
- **"Failed to add to queue"**: Server error or invalid request parameters
- **"Queue position not available"**: Queue service temporarily unavailable
- **"Failed to remove from queue"**: Request may already be processing

#### Post-Processing
- **"Source video not found"**: Video file may have been moved or deleted
- **"Python script failed"**: Check Python installation and dependencies
- **"Processing timeout"**: Large videos may take longer to process
- **"Effect already applied"**: This effect has already been applied to this video

### Performance Tips

1. **Queue Management**: Enable auto-refresh for real-time updates
2. **Large Videos**: 10-second videos take longer to process effects
3. **Multiple Effects**: Effects can be applied multiple times to the same video
4. **Storage Space**: Monitor disk usage as videos accumulate
5. **Python Performance**: Ensure sufficient RAM for video processing

## Cost Considerations

### Video Generation
- **5-second videos**: $0.18 each
- **10-second videos**: $0.36 each
- **Queue position**: No additional cost for waiting in queue

### Post-Processing
- **Local processing**: No additional API costs
- **CPU intensive**: Python processing uses local computing resources
- **Storage**: Processed videos create additional file copies

Monitor usage in FAL.ai dashboard and local storage space.

## Deployment

For local use only. To deploy:

1. Build the application:
   ```bash
   npm run build
   ```

2. Start production server:
   ```bash
   npm start
   ```

3. Ensure Python and dependencies are available in production environment

## Contributing

This is a local MVP application. For enhancements:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly (including Python components)
5. Submit a pull request

### Adding New Effects

1. Create effect processor in `scripts/`
2. Add TypeScript interfaces in `src/types/video.ts`
3. Update PostFX API routes
4. Add UI components for effect configuration
5. Update PostFXModal component

## License

This project is for personal/local use. Check FAL.ai terms for commercial usage.

## Support

- **FAL.ai Documentation**: [https://docs.fal.ai/](https://docs.fal.ai/)
- **Next.js Documentation**: [https://nextjs.org/docs](https://nextjs.org/docs)
- **OpenCV Documentation**: [https://docs.opencv.org/](https://docs.opencv.org/)
- **Issues**: Check console logs for detailed error messages

## Version History

- **v0.1.0**: Initial MVP release with image-to-video generation and gallery features
- **v0.2.0**: Added queue management system with real-time tracking
- **v0.3.0**: Introduced post-processing effects with cathode ray CRT styling
- **v0.4.0**: Enhanced UI with notifications and advanced video management
- **v0.5.0**: Enhanced video processing pipeline with FFmpeg optimization and improved error handling
  - Multi-codec fallback strategy for better video compatibility
  - FFmpeg post-processing for web-optimized video output
  - Enhanced thumbnail generation with retry logic and detailed error reporting
  - Comprehensive video validation and integrity checking
  - Improved CORS handling and caching mechanisms
- **Documentation Updated**: January 2025 - Added PostFX output format standards and comprehensive troubleshooting

## Roadmap

### Planned Features
- Additional post-processing effects (VHS, film grain, color grading)
- Batch processing capabilities
- Video export options and formats
- Effect parameter presets and sharing
- Performance optimizations for large videos
- Database integration for production deployments
