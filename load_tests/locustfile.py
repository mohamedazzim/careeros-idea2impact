from locust import HttpUser, task, between

class CareerOSUser(HttpUser):
    wait_time = between(1, 5)

    @task
    def check_health(self):
        self.client.get("/health/live")
        
    @task
    def mock_retrieval(self):
        self.client.post("/api/v1/search", json={"query": "python developer"})

    @task
    def mock_eval(self):
        self.client.post("/api/v1/evaluate", json={"resume_id": "1", "job_id": "2"})
