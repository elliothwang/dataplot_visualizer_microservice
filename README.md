# Data Plot Visualizer Microservice

A Flask-based microservice that generates and serves plot images based on input data.

The service supports two main capabilities:

1. **Generate Plot From Data** – Accepts numeric data and creates a PNG plot.
2. **Download Generated Plot** – Returns the stored PNG plot by its identifier for use in reports or presentations.

This microservice is intended to be called **programmatically** over HTTP (e.g., from your Main Program), not imported directly as a library.

---

## Table of Contents

1. [Overview](#overview)
2. [Endpoints](#endpoints)
3. [Data Model](#data-model)
4. [Running the Service](#running-the-service)
5. [Environment Variables](#environment-variables)
6. [Testing](#testing)
7. [Example Usage](#example-usage)
8. [Integration with the Main Program](#integration-with-the-main-program)
9. [Relation to User Stories](#relation-to-user-stories)

---

## Overview

This microservice is responsible for:

- Accepting numeric data (up to 5,000 points).
- Generating a line plot with consistent styling.
- Storing the generated plot as a PNG file.
- Returning a **plot identifier** to the caller.
- Serving the PNG file for download when requested by `plot_id`.

The service is deliberately kept small and stateless apart from:

- A simple in-memory index of plots (`PLOTS`).
- PNG files stored in a local directory (`PLOTS_DIR`).

---

## Endpoints

All endpoints return JSON except the image download, which returns `image/png`.

### `GET /health`

Health check for the service.

**Response (200)**

```json
{
  "status": "ok",
  "service": "data-plot-visualizer",
  "stored_plots": 0
}
