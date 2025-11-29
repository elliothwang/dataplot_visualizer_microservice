import os
import uuid
from datetime import datetime

# use a non-interactive backend for headless environments
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from flask import Flask, jsonify, request, send_file

# directory for storing generated plot images
PLOTS_DIR = os.environ.get("PLOT_SERVICE_DIR", "plots")

# simple in-memory index of generated plots
# maps plot_id -> { "path": <file_path>, "created_at": <iso8601> }
PLOTS = {}


def _ensure_plots_dir() -> None:
    """
    makes sure the plot directory exists
    """
    os.makedirs(PLOTS_DIR, exist_ok=True)


_ensure_plots_dir()

app = Flask(__name__)
app.config["JSON_SORT_KEYS"] = False  # keep response keys in defined order


# -----------------------------
# helpers
# -----------------------------


def _validate_plot_request(payload):
    """
    validates incoming plot generation payload
    returns (x_values, y_values, meta) or (None, None, error_message)
    """
    if not isinstance(payload, dict):
        return None, None, "request body must be a json object"

    data = payload.get("data")
    if data is None:
        return None, None, "missing 'data' field"

    # support either { "y": [...] } or a flat array [ ... ]
    if isinstance(data, dict):
        y = data.get("y")
        x = data.get("x")
    else:
        y = data
        x = None

    # ensure y is a list-like of numbers
    if not isinstance(y, (list, tuple)):
        return None, None, "'data' or 'data.y' must be an array of numbers"

    if len(y) < 2:
        return None, None, "at least two data points are required"

    if len(y) > 5000:
        return None, None, "data contains too many points (max 5000)"

    try:
        y_values = [float(v) for v in y]
    except (TypeError, ValueError):
        return None, None, "all y values must be numeric"

    if x is None:
        x_values = list(range(len(y_values)))
    else:
        if not isinstance(x, (list, tuple)):
            return None, None, "'data.x' must be an array of numbers"
        if len(x) != len(y_values):
            return None, None, "x and y must have the same length"
        try:
            x_values = [float(v) for v in x]
        except (TypeError, ValueError):
            return None, None, "all x values must be numeric"

    meta = {
        "title": str(payload.get("title", "Data Plot")),
        "x_label": str(payload.get("x_label", "Index")),
        "y_label": str(payload.get("y_label", "Value")),
    }

    return x_values, y_values, meta


def _generate_plot_file(x_values, y_values, meta):
    """
    generates a plot image and stores it on disk
    returns (plot_id, file_path, created_at)
    """
    plot_id = str(uuid.uuid4())
    file_name = f"{plot_id}.png"
    file_path = os.path.join(PLOTS_DIR, file_name)

    # create a new figure for each plot
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.plot(x_values, y_values, linewidth=1.8)

    ax.set_title(meta["title"])
    ax.set_xlabel(meta["x_label"])
    ax.set_ylabel(meta["y_label"])
    ax.grid(True, linewidth=0.3, alpha=0.4)

    fig.tight_layout()
    fig.savefig(file_path, dpi=120)
    plt.close(fig)

    created_at = datetime.utcnow().isoformat() + "Z"

    PLOTS[plot_id] = {
        "path": file_path,
        "created_at": created_at,
    }

    return plot_id, file_path, created_at


# -----------------------------
# routes
# -----------------------------


@app.route("/health", methods=["GET"])
def health():
    """
    health check endpoint
    """
    return jsonify(
        {
            "status": "ok",
            "service": "data-plot-visualizer",
            "stored_plots": len(PLOTS),
        }
    ), 200


@app.route("/plots", methods=["POST"])
def create_plot():
    """
    generates a plot from supplied data and stores it
    expected json body:
    {
      "data": [1, 2, 3] or { "x": [...], "y": [...] },
      "title": "optional title",
      "x_label": "optional label",
      "y_label": "optional label"
    }
    """
    if not request.is_json:
        return (
            jsonify(
                {
                    "status": "error",
                    "message": "expected json body",
                }
            ),
            400,
        )

    payload = request.get_json(silent=True)
    x_values, y_values, meta_or_error = _validate_plot_request(payload)

    if x_values is None:
        # validation failed, meta_or_error contains an error message string
        return (
            jsonify(
                {
                    "status": "error",
                    "message": meta_or_error,
                }
            ),
            400,
        )

    plot_id, file_path, created_at = _generate_plot_file(x_values, y_values, meta_or_error)

    return (
        jsonify(
            {
                "status": "ok",
                "plot_id": plot_id,
                "created_at": created_at,
                "image_path": file_path,
            }
        ),
        200,
    )


@app.route("/plots/<plot_id>", methods=["GET"])
def download_plot(plot_id):
    """
    returns the generated plot image file for download
    """
    info = PLOTS.get(plot_id)
    if not info:
        return (
            jsonify(
                {
                    "status": "error",
                    "message": f"plot '{plot_id}' not found",
                }
            ),
            404,
        )

    file_path = info.get("path")
    if not file_path or not os.path.exists(file_path):
        return (
            jsonify(
                {
                    "status": "error",
                    "message": "plot file is missing or unavailable",
                }
            ),
            500,
        )

    # send the stored png file as an attachment
    return send_file(
        file_path,
        mimetype="image/png",
        as_attachment=True,
        download_name=f"plot-{plot_id}.png",
    )


@app.errorhandler(404)
def not_found(_error):
    """
    simple 404 handler for unknown routes
    """
    return (
        jsonify(
            {
                "status": "error",
                "message": "endpoint not found",
            }
        ),
        404,
    )


def create_app():
    """
    factory used by tests or wsgi servers
    """
    return app


if __name__ == "__main__":
    port = int(os.environ.get("PLOT_SERVICE_PORT", "5006"))
    app.run(host="0.0.0.0", port=port, debug=False)
