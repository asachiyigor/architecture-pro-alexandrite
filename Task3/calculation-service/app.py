from flask import Flask, jsonify
import random
import time
import os
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.resources import Resource, SERVICE_NAME
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.flask import FlaskInstrumentor

# Configure OpenTelemetry
resource = Resource.create({SERVICE_NAME: os.getenv("SERVICE_NAME", "calculation-service")})
trace.set_tracer_provider(TracerProvider(resource=resource))

otlp_exporter = OTLPSpanExporter(
    endpoint=os.getenv("JAEGER_ENDPOINT", "localhost:4317"),
    insecure=True
)

trace.get_tracer_provider().add_span_processor(BatchSpanProcessor(otlp_exporter))

app = Flask(__name__)
FlaskInstrumentor().instrument_app(app)

tracer = trace.get_tracer(__name__)

@app.route('/calculate', methods=['GET'])
def calculate():
    with tracer.start_as_current_span("calculate_cost") as span:
        # Симуляция сложности расчета
        complexity = random.choice(["simple", "complex"])
        span.set_attribute("calculation.complexity", complexity)

        # Симуляция времени расчета (как в реальном MES 2-30 минут, здесь 0.1-1 сек для демо)
        if complexity == "simple":
            time.sleep(random.uniform(0.1, 0.3))
            cost = random.randint(5000, 15000)
            production_time = random.randint(8, 24)
        else:
            time.sleep(random.uniform(0.5, 1.0))
            cost = random.randint(15000, 50000)
            production_time = random.randint(24, 72)

        span.set_attribute("calculation.cost", cost)
        span.set_attribute("calculation.time_hours", production_time)

        result = {
            "estimated_cost": cost,
            "production_time_hours": production_time,
            "complexity": complexity
        }

        span.add_event("calculation_completed", {"result": str(result)})

        return jsonify(result), 200

@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "healthy"}), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8081)
