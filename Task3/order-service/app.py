from flask import Flask, jsonify
import requests
import random
import string
import os
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.resources import Resource, SERVICE_NAME
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.flask import FlaskInstrumentor
from opentelemetry.instrumentation.requests import RequestsInstrumentor

# Configure OpenTelemetry
resource = Resource.create({SERVICE_NAME: os.getenv("SERVICE_NAME", "order-service")})
trace.set_tracer_provider(TracerProvider(resource=resource))

otlp_exporter = OTLPSpanExporter(
    endpoint=os.getenv("JAEGER_ENDPOINT", "localhost:4317"),
    insecure=True
)

trace.get_tracer_provider().add_span_processor(BatchSpanProcessor(otlp_exporter))

app = Flask(__name__)
FlaskInstrumentor().instrument_app(app)
RequestsInstrumentor().instrument()

tracer = trace.get_tracer(__name__)

CALCULATION_SERVICE_URL = os.getenv("CALCULATION_SERVICE_URL", "http://localhost:8081")

def generate_order_id():
    return f"ORD-{''.join(random.choices(string.digits, k=5))}"

@app.route('/order', methods=['GET'])
def create_order():
    with tracer.start_as_current_span("create_order") as span:
        order_id = generate_order_id()
        span.set_attribute("order.id", order_id)
        span.set_attribute("order.status", "created")

        span.add_event("order_created", {"order_id": order_id})

        # Вызов calculation service для расчета стоимости
        try:
            with tracer.start_as_current_span("call_calculation_service") as calc_span:
                calc_span.set_attribute("http.url", f"{CALCULATION_SERVICE_URL}/calculate")

                response = requests.get(f"{CALCULATION_SERVICE_URL}/calculate", timeout=5)
                response.raise_for_status()

                calculation = response.json()
                calc_span.add_event("calculation_received", {"calculation": str(calculation)})

        except requests.exceptions.RequestException as e:
            span.record_exception(e)
            span.set_attribute("error", True)
            return jsonify({
                "error": "Failed to calculate cost",
                "order_id": order_id,
                "status": "failed"
            }), 500

        result = {
            "order_id": order_id,
            "status": "created",
            "calculation": calculation
        }

        span.add_event("order_completed", {"order": str(result)})

        return jsonify(result), 200

@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "healthy"}), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
