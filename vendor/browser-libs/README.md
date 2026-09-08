# Tray browser runtime

These amd64 shared libraries come from Debian 11 Bullseye packages. They let
Playwright Chromium run on Streamlit when the deployment host cannot complete
its normal `apt` package installation.

The bundle includes Chromium's transitive runtime dependencies, not only the
libraries linked directly by the browser executable.

Keep this bundle aligned with Streamlit's Debian release. Mixing libraries from
different Debian releases can start Chromium successfully but crash its renderer
processes during navigation.
