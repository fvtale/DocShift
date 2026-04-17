APP_STYLE = """
QMainWindow, QWidget {
    background-color: #0b0b0f;
    color: #f2f2f2;
    font-family: Segoe UI, Arial, sans-serif;
    font-size: 14px;
}

QFrame#Card {
    background-color: #111118;
    border: 1px solid #2a0f14;
    border-radius: 18px;
}

QLabel#Title {
    font-size: 24px;
    font-weight: 600;
    color: #ff4d5a;
}

QLabel#Subtitle {
    color: #b9b9c3;
}

QLineEdit {
    background-color: #09090d;
    border: 1px solid #2f1418;
    border-radius: 10px;
    padding: 10px 12px;
    color: #f7f7f7;
    selection-background-color: #8b1e2d;
}

QLineEdit:focus {
    border: 1px solid #ff4d5a;
}

QPushButton {
    background-color: #15151c;
    border: 1px solid #352026;
    border-radius: 10px;
    padding: 10px 14px;
    color: #f5f5f5;
}

QPushButton:hover {
    border: 1px solid #ff4d5a;
    background-color: #1d1216;
}

QPushButton:pressed {
    background-color: #2a0f14;
}

QPushButton#ConvertButton {
    background-color: #8b1e2d;
    border: 1px solid #ff4d5a;
    font-weight: 600;
}

QPushButton#ConvertButton:hover {
    background-color: #a32436;
}

QLabel#Status {
    color: #c7c7d1;
}
"""
