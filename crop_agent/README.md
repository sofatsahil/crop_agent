# CropManage Agricultural Assistant

## Overview
CropManage is an agricultural assistant application designed to help users manage crop recommendations effectively. It provides a menu-driven interface for users to obtain irrigation, fertilizer, and weather recommendations based on their selected crops and locations.

## Project Structure
```
crop_agent/
├── main.py            # Main entry point of the application
├── api_handler.py     # Functions for user authentication and data retrieval
├── tts_engine.py      # Text-to-speech functionality
├── requirements.txt    # Project dependencies
├── .env               # Environment variables for authentication
└── README.md          # Project documentation
```

## Setup Instructions

1. **Clone the Repository**
   ```
   git clone <repository-url>
   cd crop_agent
   ```

2. **Create a Virtual Environment**
   ```
   python -m venv venv
   source venv/bin/activate  # On Windows use `venv\Scripts\activate`
   ```

3. **Install Dependencies**
   ```
   pip install -r requirements.txt
   ```

4. **Configure Environment Variables**
   Create a `.env` file in the root directory and add your credentials:
   ```
   CROP_USERNAME=your_username
   CROP_PASSWORD=your_password
   ```

## Usage
To run the application, execute the following command:
```
python main.py
```

Follow the on-screen instructions to navigate through the menu and obtain crop recommendations.

## Contributing
Contributions are welcome! Please open an issue or submit a pull request for any enhancements or bug fixes.

## License
This project is licensed under the MIT License. See the LICENSE file for more details.