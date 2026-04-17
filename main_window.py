from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)
from app.converter import convert_pdf_to_docx
from app.style import APP_STYLE


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('PDF to DOCX')
        self.setMinimumSize(640, 360)
        self.setStyleSheet(APP_STYLE)
        self._build_ui()

    def _build_ui(self):
        root = QWidget()
        self.setCentralWidget(root)

        outer = QVBoxLayout(root)
        outer.setContentsMargins(24, 24, 24, 24)
        outer.setSpacing(0)

        card = QFrame()
        card.setObjectName('Card')
        outer.addWidget(card)

        layout = QVBoxLayout(card)
        layout.setContentsMargins(26, 26, 26, 26)
        layout.setSpacing(18)

        title = QLabel('PDF to DOCX')
        title.setObjectName('Title')
        subtitle = QLabel('Minimal conversion, dark interface, fast workflow.')
        subtitle.setObjectName('Subtitle')

        layout.addWidget(title)
        layout.addWidget(subtitle)

        grid = QGridLayout()
        grid.setHorizontalSpacing(12)
        grid.setVerticalSpacing(12)

        self.pdf_edit = QLineEdit()
        self.pdf_edit.setPlaceholderText('Select a PDF file...')
        pdf_btn = QPushButton('Browse')
        pdf_btn.clicked.connect(self.pick_pdf)

        self.out_edit = QLineEdit()
        self.out_edit.setPlaceholderText('Choose output folder...')
        out_btn = QPushButton()
        out_btn.setToolTip('Choose output folder')
        out_btn.setText('📁')
        out_btn.setFixedWidth(52)
        out_btn.clicked.connect(self.pick_output_folder)

        grid.addWidget(QLabel('Input PDF'), 0, 0)
        grid.addWidget(self.pdf_edit, 1, 0)
        grid.addWidget(pdf_btn, 1, 1)
        grid.addWidget(QLabel('Output Folder'), 2, 0)
        grid.addWidget(self.out_edit, 3, 0)
        grid.addWidget(out_btn, 3, 1)

        layout.addLayout(grid)

        bottom = QHBoxLayout()
        self.status = QLabel('Ready.')
        self.status.setObjectName('Status')
        self.convert_btn = QPushButton('Convert to DOCX')
        self.convert_btn.setObjectName('ConvertButton')
        self.convert_btn.clicked.connect(self.convert_file)

        bottom.addWidget(self.status, 1)
        bottom.addWidget(self.convert_btn)
        layout.addLayout(bottom)

    def pick_pdf(self):
        path, _ = QFileDialog.getOpenFileName(self, 'Select PDF', '', 'PDF Files (*.pdf)')
        if path:
            self.pdf_edit.setText(path)

    def pick_output_folder(self):
        path = QFileDialog.getExistingDirectory(self, 'Select Output Folder')
        if path:
            self.out_edit.setText(path)

    def convert_file(self):
        pdf_path = self.pdf_edit.text().strip()
        out_dir = self.out_edit.text().strip()

        if not pdf_path or not out_dir:
            QMessageBox.warning(self, 'Missing Info', 'Please choose both a PDF file and an output folder.')
            return

        self.status.setText('Converting...')
        self.convert_btn.setEnabled(False)
        QApplication.processEvents()

        try:
            output_path = convert_pdf_to_docx(pdf_path, out_dir)
            self.status.setText(f'Done: {output_path}')
            QMessageBox.information(self, 'Success', f'Created:
{output_path}')
        except Exception as e:
            self.status.setText('Conversion failed.')
            QMessageBox.critical(self, 'Error', str(e))
        finally:
            self.convert_btn.setEnabled(True)
