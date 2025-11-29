import os
import shutil
import unittest

# configure plots directory before importing app
os.environ["PLOT_SERVICE_DIR"] = "test_plots"

from app import create_app, PLOTS, PLOTS_DIR  # noqa: E402


class DataPlotVisualizerTests(unittest.TestCase):
    """
    integration-style tests for the data plot visualizer microservice
    """

    def setUp(self):
        # fresh app + client each test
        self.app = create_app()
        self.client = self.app.test_client()

        # reset in-memory plot index
        PLOTS.clear()

        # ensure clean plots dir
        if os.path.exists(PLOTS_DIR):
            shutil.rmtree(PLOTS_DIR)
        os.makedirs(PLOTS_DIR, exist_ok=True)

    def tearDown(self):
        # clean up generated files
        if os.path.exists(PLOTS_DIR):
            shutil.rmtree(PLOTS_DIR)

    # ------------------------
    # helpers
    # ------------------------

    def _generate_sample_plot(self):
        payload = {
            "data": [1, 2, 3, 4, 5],
            "title": "Sample Plot",
            "x_label": "Index",
            "y_label": "Value",
        }
        resp = self.client.post("/plots", json=payload)
        self.assertEqual(resp.status_code, 200)
        body = resp.get_json()
        self.assertEqual(body.get("status"), "ok")
        plot_id = body.get("plot_id")
        self.assertIsNotNone(plot_id)
        return plot_id, body

    # ------------------------
    # tests
    # ------------------------

    def test_health_endpoint_reports_ok_and_count(self):
        resp = self.client.get("/health")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()

        self.assertEqual(data.get("status"), "ok")
        self.assertEqual(data.get("service"), "data-plot-visualizer")
        self.assertIn("stored_plots", data)

    def test_generate_plot_with_simple_y_array(self):
        payload = {
            "data": [0, 1, 4, 9, 16],
            "title": "Squares",
            "x_label": "n",
            "y_label": "n^2",
        }
        resp = self.client.post("/plots", json=payload)
        self.assertEqual(resp.status_code, 200)

        data = resp.get_json()
        self.assertEqual(data.get("status"), "ok")
        plot_id = data.get("plot_id")
        image_path = data.get("image_path")

        self.assertIsInstance(plot_id, str)
        self.assertTrue(os.path.exists(image_path))
        self.assertIn(plot_id, PLOTS)

    def test_generate_plot_with_x_and_y_arrays(self):
        payload = {
            "data": {
                "x": [0, 1, 2, 3],
                "y": [1.0, 2.0, 3.0, 4.5],
            },
            "title": "Custom Axes",
            "x_label": "Time (s)",
            "y_label": "Reading",
        }
        resp = self.client.post("/plots", json=payload)
        self.assertEqual(resp.status_code, 200)

        data = resp.get_json()
        self.assertEqual(data.get("status"), "ok")
        plot_id = data.get("plot_id")
        image_path = data.get("image_path")

        self.assertIsInstance(plot_id, str)
        self.assertTrue(os.path.exists(image_path))
        self.assertIn(plot_id, PLOTS)

    def test_generate_plot_rejects_non_json_body(self):
        resp = self.client.post("/plots", data="not-json", content_type="text/plain")
        self.assertEqual(resp.status_code, 400)

        data = resp.get_json()
        self.assertEqual(data.get("status"), "error")
        self.assertIn("expected json body", data.get("message", "").lower())

    def test_generate_plot_rejects_missing_data_field(self):
        resp = self.client.post("/plots", json={"title": "no data"})
        self.assertEqual(resp.status_code, 400)

        data = resp.get_json()
        self.assertEqual(data.get("status"), "error")
        self.assertIn("missing 'data' field", data.get("message", "").lower())

    def test_generate_plot_rejects_non_numeric_y(self):
        payload = {"data": ["a", "b", "c"]}
        resp = self.client.post("/plots", json=payload)
        self.assertEqual(resp.status_code, 400)

        data = resp.get_json()
        self.assertEqual(data.get("status"), "error")
        self.assertIn("all y values must be numeric", data.get("message", "").lower())

    def test_generate_plot_rejects_too_many_points(self):
        payload = {"data": list(range(5001))}
        resp = self.client.post("/plots", json=payload)
        self.assertEqual(resp.status_code, 400)

        data = resp.get_json()
        self.assertEqual(data.get("status"), "error")
        self.assertIn("too many points", data.get("message", "").lower())

    def test_generate_plot_rejects_mismatched_x_y_lengths(self):
        payload = {
            "data": {
                "x": [0, 1, 2],
                "y": [0, 1],
            }
        }
        resp = self.client.post("/plots", json=payload)
        self.assertEqual(resp.status_code, 400)

        data = resp.get_json()
        self.assertEqual(data.get("status"), "error")
        self.assertIn("same length", data.get("message", "").lower())

    def test_download_existing_plot_returns_png(self):
        plot_id, body = self._generate_sample_plot()
        image_path = body.get("image_path")
        self.assertTrue(os.path.exists(image_path))

        resp = self.client.get(f"/plots/{plot_id}")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.content_type, "image/png")

        # content should not be empty
        self.assertGreater(len(resp.data), 0)

        # close response to avoid unclosed file warnings
        resp.close()

    def test_download_missing_plot_returns_404(self):
        resp = self.client.get("/plots/does-not-exist")
        self.assertEqual(resp.status_code, 404)

        data = resp.get_json()
        self.assertEqual(data.get("status"), "error")
        self.assertIn("not found", data.get("message", "").lower())

    def test_unknown_route_returns_json_404(self):
        resp = self.client.get("/unknown/endpoint")
        self.assertEqual(resp.status_code, 404)

        data = resp.get_json()
        self.assertEqual(data.get("status"), "error")
        self.assertIn("endpoint not found", data.get("message", "").lower())


if __name__ == "__main__":
    # running as a script will execute all tests and exit with pass/fail status
    unittest.main()
