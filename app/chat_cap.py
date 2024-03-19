import sys
from PyQt5.QtWidgets import QApplication, QMainWindow, QWidget, QVBoxLayout, QLabel
from PyQt5.QtCore import QTimer
import vlc

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        # Create VLC instance
        self.instance = vlc.Instance('--no-xlib')
        
        # Create media player
        self.player = self.instance.media_player_new()
        
        # Load media
        self.media = self.instance.media_new('/home/piswitch/Apps/sb-audio/2-Charlie_Calls_Olive.mp3')
        
        # Set media to player
        self.player.set_media(self.media)
        
        # Create caption label
        self.caption_label = QLabel()
        
        # Create layout
        layout = QVBoxLayout()
        layout.addWidget(self.caption_label)

        self.caption_label.setText("Now see this")
        
        # Create central widget
        central_widget = QWidget()
        central_widget.setLayout(layout)
        self.setCentralWidget(central_widget)
        
        # Start playing the media
        self.player.play()
        
        # Start displaying captions
        self.display_captions('captions/test.srt')

    def display_captions(self, caption_file):
        with open(caption_file, 'r') as f:
            captions = f.read().split('\n\n')

        self.caption_index = 0

        def time_str_to_ms(time_str):
            hours, minutes, seconds_ms = time_str.split(':')
            seconds, milliseconds = seconds_ms.split(',')
            return int(hours) * 3600000 + int(minutes) * 60000 + int(seconds) * 1000 + int(milliseconds)

        def display_next_caption():
            print('got to display_next_caption')
            nonlocal self
            if self.caption_index < len(captions):
                caption = captions[self.caption_index]
                print(f'full entry: {caption}')
                if '-->' in caption:
                    time, text = caption.split('\n', 1)
                    print(f'time: {time}, text: {text}')
                    self.caption_label.setText(text)

                    # Proccess time
                    times = time.split(' --> ')
                    print(f'times[0]: {times[0]}')
                    start_time_ms = time_str_to_ms(times[0])
                    end_time_ms = time_str_to_ms(times[1])
                    duration_ms = end_time_ms - start_time_ms

                    QTimer.singleShot(duration_ms, display_next_caption)
                self.caption_index += 1

        display_next_caption()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
