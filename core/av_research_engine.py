import os
from datetime import datetime

class ResearchEngine:
    """A clean, minimal research engine for AV technology topics."""

    def __init__(self):
        self.knowledge_base = {
            'AEC': {
                'description': 'Acoustic Echo Cancellation (AEC) is a technology that removes acoustic echo from audio signals in real-time communication systems.',
                'principles': [
                    'Adaptive filtering using NLMS (Normalized Least Mean Squares) algorithm',
                    'Double-talk detection to prevent filter divergence',
                    'Residual echo suppression for enhanced performance',
                    'Convergence tracking and filter adaptation'
                ],
                'algorithms': [
                    'NLMS adaptive filter with variable step size',
                    'Double-talk detector based on correlation analysis',
                    'Residual echo suppressor using spectral subtraction'
                ],
                'scenarios': [
                    'Real-time voice and video calls',
                    'Conference room audio systems',
                    'Hands-free communication devices',
                    'Smart speakers and voice assistants'
                ]
            },
            'ANS': {
                'description': 'Active Noise Suppression (ANS) reduces background noise from audio signals to improve speech clarity and listening experience.',
                'principles': [
                    'Spectral subtraction for noise estimation',
                    'Wiener filtering for optimal noise reduction',
                    'Noise floor estimation and adaptation',
                    'Frequency-domain processing for real-time performance'
                ],
                'algorithms': [
                    'Spectral subtraction with over-subtraction factor',
                    'Wiener filter with noise power spectral density estimation',
                    'Minimum statistics noise estimation',
                    'MMSE-STSA (Minimum Mean Square Error - Short Time Spectral Amplitude)'
                ],
                'scenarios': [
                    'Noisy environment voice communication',
                    'Audio recording and post-processing',
                    'Hearing aid and assistive listening devices',
                    'Automotive in-cabin audio systems'
                ]
            },
            'codec': {
                'description': 'Audio and video codecs compress and decompress digital media for efficient storage and transmission.',
                'principles': [
                    'Lossy and lossless compression techniques',
                    'Transform coding using DCT/MDCT',
                    'Motion estimation and compensation for video',
                    'Entropy coding (Huffman, arithmetic coding)'
                ],
                'algorithms': [
                    'H.264/AVC with macroblock-based motion compensation',
                    'H.265/HEVC with coding tree units',
                    'Opus audio codec with SILK and CELT modes',
                    'AAC with MDCT-based spectral coding'
                ],
                'scenarios': [
                    'Video streaming and conferencing',
                    'Audio streaming and podcasting',
                    'Digital television and broadcasting',
                    'Video surveillance and storage'
                ]
            },
            'rtp_rtcp': {
                'description': 'Real-time Transport Protocol (RTP) and Real-time Transport Control Protocol (RTCP) provide end-to-end delivery services and quality feedback for real-time audio and video data over IP networks.',
                'principles': [
                    'Packetization of media streams with timestamps',
                    'Sequence numbering for packet ordering and loss detection',
                    'Payload type identification for codec negotiation',
                    'Synchronization source (SSRC) for stream identification',
                    'Sender reports (SR) with transmission statistics',
                    'Receiver reports (RR) with reception quality metrics',
                    'Source description (SDES) items for participant identification',
                    'Bye packets for session termination'
                ],
                'algorithms': [
                    'RTP packet header construction and parsing',
                    'Jitter buffer management for playout synchronization',
                    'Payload format specific to codecs (e.g., RFC 3551)',
                    'RTCP sender and receiver report generation',
                    'RTCP report interval calculation based on RFC 3550',
                    'Packet loss rate and jitter computation',
                    'Round-trip time estimation from SR/RR timestamps',
                    'Compound RTCP packet construction'
                ],
                'scenarios': [
                    'VoIP and video conferencing systems',
                    'Live streaming and broadcasting',
                    'WebRTC browser-based communication',
                    'IPTV and multimedia distribution',
                    'Quality monitoring in VoIP systems',
                    'Adaptive bitrate streaming based on network conditions',
                    'Conference management with participant statistics',
                    'Network diagnostics and troubleshooting'
                ]
            }
        }

    def research(self, topic: str) -> str:
        """Generate a structured markdown report for the given topic."""
        topic_lower = topic.lower().strip()
        
        # Resolve topic to known keys
        resolved_topic = None
        for key in self.knowledge_base:
            if topic_lower == key.lower():
                resolved_topic = key
                break
            # Check if topic is a known alias
            if topic_lower in ['acoustic echo cancellation', 'echo cancellation'] and key == 'AEC':
                resolved_topic = 'AEC'
                break
            if topic_lower in ['active noise suppression', 'noise reduction'] and key == 'ANS':
                resolved_topic = 'ANS'
                break
            if topic_lower in ['codec', 'codecs', 'audio codec', 'video codec'] and key == 'codec':
                resolved_topic = 'codec'
                break
            if topic_lower in ['rtp', 'rtcp', 'rtp/rtcp', 'real-time transport protocol', 'real-time transport control protocol'] and key == 'rtp_rtcp':
                resolved_topic = 'rtp_rtcp'
                break

        if resolved_topic is None:
            available = ', '.join(self.knowledge_base.keys())
            return "Error: Unknown topic '" + topic + "'. Available topics: " + available

        info = self.knowledge_base[resolved_topic]
        
        # Build markdown report using .format() to avoid f-string issues
        report_lines = []
        report_lines.append("# Research Report: {0}".format(resolved_topic))
        report_lines.append("")
        report_lines.append("**Generated:** {0}".format(datetime.now().strftime('%Y-%m-%d %H:%M:%S')))
        report_lines.append("")
        report_lines.append("## Summary")
        report_lines.append(info['description'])
        report_lines.append("")
        report_lines.append("## Technical Principles")
        for principle in info['principles']:
            report_lines.append("- {0}".format(principle))
        report_lines.append("")
        report_lines.append("## Algorithm Details")
        for algo in info['algorithms']:
            report_lines.append("- {0}".format(algo))
        report_lines.append("")
        report_lines.append("## Application Scenarios")
        for scenario in info['scenarios']:
            report_lines.append("- {0}".format(scenario))
        report_lines.append("")
        
        report = "\n".join(report_lines)
        
        # Write report to file
        reports_dir = 'reports/av-research'
        os.makedirs(reports_dir, exist_ok=True)
        report_file = os.path.join(reports_dir, "{0}_report.md".format(resolved_topic.lower()))
        with open(report_file, 'w', encoding='utf-8') as f:
            f.write(report)
        
        return report

    def list_topics(self) -> list:
        """Return list of available research topics."""
        return list(self.knowledge_base.keys())

    def get_topic_info(self, topic: str) -> dict:
        """Return detailed information about a topic."""
        topic_lower = topic.lower().strip()
        for key in self.knowledge_base:
            if topic_lower == key.lower():
                return self.knowledge_base[key]
        return {}