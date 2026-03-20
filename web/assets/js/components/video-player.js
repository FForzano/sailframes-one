/**
 * VideoPlayer - HLS video playback synchronized with timeline
 */
class VideoPlayer {
    constructor() {
        this.players = {
            cockpit: null,
            sails: null
        };
        this.hlsInstances = {
            cockpit: null,
            sails: null
        };
        this.videoElements = {
            cockpit: document.getElementById('video-cockpit'),
            sails: document.getElementById('video-sails')
        };
        this.videoContainer = document.getElementById('video-container');
        this.streamInfo = null;
        this.sessionStart = null;
        this.isSeeking = false;

        this._setupTimeSync();
    }

    _setupTimeSync() {
        window.timeController.addEventListener('time-change', (e) => {
            if (!this.isSeeking) {
                this.syncToTime(e.detail.time);
            }
        });

        window.timeController.addEventListener('play', () => {
            this.play();
        });

        window.timeController.addEventListener('pause', () => {
            this.pause();
        });
    }

    /**
     * Load video streams for a session
     */
    async loadStreams(deviceId, date) {
        try {
            const response = await fetch(`/api/video/${deviceId}/${date}`);
            if (!response.ok) {
                console.warn('No video available for this session');
                this.videoContainer.style.display = 'none';
                return;
            }

            const data = await response.json();
            this.streamInfo = data.streams;

            // Check if any streams available
            const hasStreams = Object.values(this.streamInfo).some(s => s && s.playlist_url);
            if (!hasStreams) {
                this.videoContainer.style.display = 'none';
                return;
            }

            this.videoContainer.style.display = 'flex';

            // Initialize HLS for each stream
            for (const [camera, info] of Object.entries(this.streamInfo)) {
                if (info && info.playlist_url) {
                    this._initHLS(camera, info);
                }
            }
        } catch (error) {
            console.error('Error loading video streams:', error);
            this.videoContainer.style.display = 'none';
        }
    }

    _initHLS(camera, streamInfo) {
        const video = this.videoElements[camera];
        if (!video) return;

        // Destroy existing HLS instance
        if (this.hlsInstances[camera]) {
            this.hlsInstances[camera].destroy();
        }

        if (Hls.isSupported()) {
            const hls = new Hls({
                enableWorker: true,
                lowLatencyMode: false
            });

            hls.loadSource(streamInfo.playlist_url);
            hls.attachMedia(video);

            hls.on(Hls.Events.MANIFEST_PARSED, () => {
                console.log(`HLS manifest loaded for ${camera}`);
            });

            hls.on(Hls.Events.ERROR, (event, data) => {
                if (data.fatal) {
                    console.error(`HLS fatal error for ${camera}:`, data);
                }
            });

            this.hlsInstances[camera] = hls;
        } else if (video.canPlayType('application/vnd.apple.mpegurl')) {
            // Native HLS support (Safari)
            video.src = streamInfo.playlist_url;
        }

        // Store stream start time for sync
        if (streamInfo.start_time) {
            video.dataset.startTime = streamInfo.start_time;
        }
    }

    /**
     * Sync video position to current time
     */
    syncToTime(time) {
        if (!time || !this.streamInfo) return;

        for (const [camera, info] of Object.entries(this.streamInfo)) {
            if (!info || !info.start_time) continue;

            const video = this.videoElements[camera];
            if (!video || video.readyState < 2) continue;

            const streamStart = new Date(info.start_time).getTime();
            const targetMs = time.getTime();

            // Calculate offset from stream start
            const offsetSeconds = (targetMs - streamStart) / 1000;

            // Only seek if video is loaded and offset is valid
            if (offsetSeconds >= 0 && offsetSeconds <= video.duration) {
                // Avoid seeking if already close
                if (Math.abs(video.currentTime - offsetSeconds) > 1) {
                    this.isSeeking = true;
                    video.currentTime = offsetSeconds;
                    setTimeout(() => { this.isSeeking = false; }, 100);
                }
            }
        }
    }

    /**
     * Play all videos
     */
    play() {
        Object.values(this.videoElements).forEach(video => {
            if (video && video.readyState >= 2) {
                video.play().catch(() => {});
            }
        });
    }

    /**
     * Pause all videos
     */
    pause() {
        Object.values(this.videoElements).forEach(video => {
            if (video) {
                video.pause();
            }
        });
    }

    /**
     * Set playback rate
     */
    setPlaybackRate(rate) {
        Object.values(this.videoElements).forEach(video => {
            if (video) {
                video.playbackRate = rate;
            }
        });
    }

    /**
     * Cleanup
     */
    destroy() {
        Object.values(this.hlsInstances).forEach(hls => {
            if (hls) hls.destroy();
        });
        this.hlsInstances = { cockpit: null, sails: null };
    }
}

window.VideoPlayer = VideoPlayer;
