# 🎬 Vizen Watchlist
[<img src="logo.png" align="right" width="150">](https://github.com/xHashii/Vizen-Watchlist)

**The most elegant way to track your Asian Drama journey.**

![Version](https://img.shields.io/badge/version-1.2.1-ff4da6?style=for-the-badge)
![Platform](https://img.shields.io/badge/platform-windows-00a2ed?style=for-the-badge)
![License](https://img.shields.io/badge/license-MIT-green?style=for-the-badge)

Vizen is a high-performance desktop application built for drama enthusiasts. Whether you are into K-Dramas, J-Dramas, C-Dramas, or Thai Lakorns, Vizen provides a buttery-smooth interface to search, track, and rate your favorite shows.

---

## ✨ Key Features

*   **🌏 Pan-Asian Search:** Powered by TMDB, search thousands of titles across Korea, Japan, China, Thailand, Taiwan, Hong Kong, and more.
*   **⚡ Zero-Lag UI:** Optimized with a staggered loading engine and background thread pool to ensure a 60fps experience even with hundreds of shows.
*   **💾 Smart Caching:** Posters are automatically cached locally as optimized JPGs, saving up to 80% disk space and allowing near-instant load times.
*   **💖 Heart Rating System:** An elegant, pink-themed 5-heart rating system to keep track of your all-time favorites.
*   **🌓 AMOLED Mode:** Switch between a deep purple "Vizen" theme and a pure black "AMOLED" theme for high-contrast displays.
*   **🚀 Auto-Updates:** Built-in GitHub integration checks for new releases and installs them automatically.
*   **📦 Data Portability:** Easily backup and restore your entire library using the JSON Import/Export feature.

---

## 📸 Screenshots

| Browse Tab | Library View | Drama Details |
| :--- | :--- | :--- |
| ![Browse](https://raw.githubusercontent.com/xHashii/Vizen-Watchlist/main/screenshots/browse.png) | ![Library](https://raw.githubusercontent.com/xHashii/Vizen-Watchlist/main/screenshots/library.png) | ![Details](https://raw.githubusercontent.com/xHashii/Vizen-Watchlist/main/screenshots/details.png) |

---

## 🚀 Installation

1.  Head over to the [**Releases**](https://github.com/xHashii/Vizen-Watchlist/releases) page.
2.  Download the latest `Vizen_Setup.exe`.
3.  Run the installer and follow the prompts.
4.  Launch **Vizen** from your desktop or start menu.

---

## 🛠️ Development Setup

If you want to contribute or run the application from the source code:

### Prerequisites
- Python 3.10 or higher
- A TMDB API Key (Bearer Token)

### Setup
1.  **Clone the repository:**
    ```bash
    git clone https://github.com/xHashii/Vizen-Watchlist.git
    cd Vizen-Watchlist
    ```

2.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

3.  **Configure API Key:**
    Create a `config.json` file in the root directory:
    ```json
    {
      "api_key": "YOUR_TMDB_BEARER_TOKEN_HERE"
    }
    ```

4.  **Run the app:**
    ```bash
    python Vizen.py
    ```

---

## 🧰 Tech Stack

- **UI Framework:** [PySide6](https://www.qt.io/qt-for-python) (Qt for Python)
- **Component Library:** [PyQt-Fluent-Widgets](https://github.com/zhiyiYo/PyQt-Fluent-Widgets)
- **Database:** SQLite3
- **API:** [The Movie Database (TMDB)](https://www.themoviedb.org/)
- **Installer:** Inno Setup

---

## 👤 Credits

Developed with ❤️ by **Hashii**.

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

### ⚠️ Disclaimer
*Vizen uses the TMDB API but is not endorsed or certified by TMDB. This application is for personal use only.*