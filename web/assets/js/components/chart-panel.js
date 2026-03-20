/**
 * ChartPanel - Time-series charts with Chart.js
 */
class ChartPanel {
    constructor() {
        this.charts = {};
        this.data = {};
        this.dataIndex = {};
        this.verticalLinePlugin = this._createVerticalLinePlugin();

        this._init();
        this._setupTimeSync();
    }

    _createVerticalLinePlugin() {
        return {
            id: 'verticalLine',
            afterDraw: (chart) => {
                if (chart.verticalLineX === undefined) return;

                const ctx = chart.ctx;
                const x = chart.verticalLineX;
                const topY = chart.chartArea.top;
                const bottomY = chart.chartArea.bottom;

                ctx.save();
                ctx.beginPath();
                ctx.moveTo(x, topY);
                ctx.lineTo(x, bottomY);
                ctx.lineWidth = 2;
                ctx.strokeStyle = '#00ba7c';
                ctx.stroke();
                ctx.restore();
            }
        };
    }

    _init() {
        const chartOptions = {
            responsive: true,
            maintainAspectRatio: false,
            animation: false,
            plugins: {
                legend: {
                    display: true,
                    position: 'top',
                    labels: {
                        color: '#8b98a5',
                        boxWidth: 12,
                        padding: 8,
                        font: { size: 10 }
                    }
                },
                tooltip: { enabled: false }
            },
            scales: {
                x: {
                    display: false
                },
                y: {
                    ticks: { color: '#8b98a5', font: { size: 10 } },
                    grid: { color: 'rgba(47, 51, 54, 0.5)' }
                }
            },
            elements: {
                point: { radius: 0 },
                line: { borderWidth: 2 }
            }
        };

        // Attitude chart (heel/pitch)
        this.charts.attitude = new Chart(
            document.getElementById('chart-attitude'),
            {
                type: 'line',
                data: {
                    labels: [],
                    datasets: [
                        {
                            label: 'Heel',
                            data: [],
                            borderColor: '#1d9bf0',
                            backgroundColor: 'rgba(29, 155, 240, 0.1)',
                            fill: true
                        },
                        {
                            label: 'Pitch',
                            data: [],
                            borderColor: '#ffad1f',
                            backgroundColor: 'transparent'
                        }
                    ]
                },
                options: {
                    ...chartOptions,
                    scales: {
                        ...chartOptions.scales,
                        y: {
                            ...chartOptions.scales.y,
                            min: -30,
                            max: 30
                        }
                    }
                },
                plugins: [this.verticalLinePlugin]
            }
        );

        // Wind chart
        this.charts.wind = new Chart(
            document.getElementById('chart-wind'),
            {
                type: 'line',
                data: {
                    labels: [],
                    datasets: [
                        {
                            label: 'AWS (kn)',
                            data: [],
                            borderColor: '#00ba7c',
                            backgroundColor: 'rgba(0, 186, 124, 0.1)',
                            fill: true,
                            yAxisID: 'y'
                        },
                        {
                            label: 'AWA',
                            data: [],
                            borderColor: '#f4212e',
                            backgroundColor: 'transparent',
                            yAxisID: 'y1'
                        }
                    ]
                },
                options: {
                    ...chartOptions,
                    scales: {
                        x: { display: false },
                        y: {
                            position: 'left',
                            ticks: { color: '#8b98a5', font: { size: 10 } },
                            grid: { color: 'rgba(47, 51, 54, 0.5)' },
                            min: 0,
                            max: 30
                        },
                        y1: {
                            position: 'right',
                            ticks: { color: '#8b98a5', font: { size: 10 } },
                            grid: { display: false },
                            min: 0,
                            max: 180
                        }
                    }
                },
                plugins: [this.verticalLinePlugin]
            }
        );

        // Speed chart
        this.charts.speed = new Chart(
            document.getElementById('chart-speed'),
            {
                type: 'line',
                data: {
                    labels: [],
                    datasets: [
                        {
                            label: 'SOG (kn)',
                            data: [],
                            borderColor: '#1d9bf0',
                            backgroundColor: 'rgba(29, 155, 240, 0.1)',
                            fill: true
                        }
                    ]
                },
                options: {
                    ...chartOptions,
                    scales: {
                        ...chartOptions.scales,
                        y: {
                            ...chartOptions.scales.y,
                            min: 0
                        }
                    }
                },
                plugins: [this.verticalLinePlugin]
            }
        );

        // Pressure chart
        this.charts.pressure = new Chart(
            document.getElementById('chart-pressure'),
            {
                type: 'line',
                data: {
                    labels: [],
                    datasets: [
                        {
                            label: 'hPa',
                            data: [],
                            borderColor: '#9333ea',
                            backgroundColor: 'rgba(147, 51, 234, 0.1)',
                            fill: true
                        }
                    ]
                },
                options: chartOptions,
                plugins: [this.verticalLinePlugin]
            }
        );
    }

    _setupTimeSync() {
        window.timeController.addEventListener('time-change', (e) => {
            this.updateCursor(e.detail.time);
        });
    }

    /**
     * Load session data
     */
    setData(sessionData) {
        const data = sessionData.data || [];

        // Reset
        this.data = {};
        this.dataIndex = {};

        // Extract data arrays
        const labels = [];
        const imuHeel = [], imuPitch = [];
        const windAws = [], windAwa = [];
        const gpsSpeed = [];
        const pressure = [];

        data.forEach((point, i) => {
            labels.push(point.t);
            this.dataIndex[point.t.substring(0, 19)] = i;

            // IMU
            if (point.imu) {
                imuHeel.push(point.imu.heel);
                imuPitch.push(point.imu.pitch);
            } else {
                imuHeel.push(null);
                imuPitch.push(null);
            }

            // Wind
            if (point.wind) {
                windAws.push(point.wind.aws_kn);
                windAwa.push(point.wind.awa);
            } else {
                windAws.push(null);
                windAwa.push(null);
            }

            // GPS
            if (point.gps) {
                gpsSpeed.push(point.gps.speed_kn);
            } else {
                gpsSpeed.push(null);
            }

            // Pressure
            if (point.pressure) {
                pressure.push(point.pressure.hpa);
            } else {
                pressure.push(null);
            }
        });

        this.data.labels = labels;

        // Update charts
        this.charts.attitude.data.labels = labels;
        this.charts.attitude.data.datasets[0].data = imuHeel;
        this.charts.attitude.data.datasets[1].data = imuPitch;
        this.charts.attitude.update('none');

        this.charts.wind.data.labels = labels;
        this.charts.wind.data.datasets[0].data = windAws;
        this.charts.wind.data.datasets[1].data = windAwa;
        this.charts.wind.update('none');

        this.charts.speed.data.labels = labels;
        this.charts.speed.data.datasets[0].data = gpsSpeed;
        this.charts.speed.update('none');

        this.charts.pressure.data.labels = labels;
        this.charts.pressure.data.datasets[0].data = pressure;
        this.charts.pressure.update('none');
    }

    /**
     * Update cursor position on all charts
     */
    updateCursor(time) {
        if (!time || !this.data.labels) return;

        const timeStr = time.toISOString().substring(0, 19);
        let index = this.dataIndex[timeStr];

        if (index === undefined) {
            // Find closest
            index = this._findClosestIndex(time);
        }

        if (index === undefined) return;

        // Update vertical line on each chart
        Object.values(this.charts).forEach(chart => {
            const meta = chart.getDatasetMeta(0);
            if (meta.data[index]) {
                chart.verticalLineX = meta.data[index].x;
                chart.draw();
            }
        });
    }

    _findClosestIndex(time) {
        if (!this.data.labels || this.data.labels.length === 0) return undefined;

        const targetMs = time.getTime();
        let closest = 0;
        let minDiff = Infinity;

        this.data.labels.forEach((label, i) => {
            const diff = Math.abs(new Date(label).getTime() - targetMs);
            if (diff < minDiff) {
                minDiff = diff;
                closest = i;
            }
        });

        return closest;
    }
}

window.ChartPanel = ChartPanel;
