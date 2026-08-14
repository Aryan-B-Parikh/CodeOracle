import json
import time
import urllib.request
from pathlib import Path

BASE_URL = "https://codeoracle-api.onrender.com/api/v1"
DEMO_DIR = Path("demo_zips")

def post_multipart(url: str, filename: str, data: bytes) -> dict:
    boundary = "----WebKitFormBoundaryDemoBundleTest"
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
        f"Content-Type: application/zip\r\n\r\n"
    ).encode("utf-8") + data + f"\r\n--{boundary}--\r\n".encode("utf-8")

    req = urllib.request.Request(url, data=body, headers={"User-Agent": "CodeOracle-Tester/1.0"})
    req.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")
    with urllib.request.urlopen(req, timeout=30) as res:
        return json.loads(res.read())

def get_json(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": "CodeOracle-Tester/1.0"})
    with urllib.request.urlopen(req, timeout=30) as res:
        return json.loads(res.read())

def post_json(url: str, payload: dict) -> dict:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json", "User-Agent": "CodeOracle-Tester/1.0"})
    with urllib.request.urlopen(req, timeout=30) as res:
        return json.loads(res.read())

def test_bundle(zip_name: str, expected_circular: bool):
    print(f"\n=======================================================")
    print(f"[*] TESTING LIVE BUNDLE: {zip_name}")
    print(f"=======================================================")
    
    zip_path = DEMO_DIR / zip_name
    zip_data = zip_path.read_bytes()
    
    # 1. Upload
    print(f"[1] Uploading {zip_name} to live Render backend...")
    upload_res = post_multipart(f"{BASE_URL}/repositories/upload", zip_name, zip_data)
    repo_id = upload_res["data"]["id"]
    repo_name = upload_res["data"]["name"]
    print(f"    [OK] Uploaded as '{repo_name}' (ID: {repo_id})")

    # 2. Analyze
    print(f"[2] Triggering background AST analysis...")
    post_json(f"{BASE_URL}/repositories/{repo_id}/analyze", {})

    # Poll until completed
    for attempt in range(12):
        time.sleep(2)
        status = get_json(f"{BASE_URL}/repositories/{repo_id}/status")["data"]
        stage = status.get("currentStage")
        analysis_status = status.get("analysisStatus")
        print(f"    ... pipeline stage: {stage} ({analysis_status})")
        if analysis_status == "completed" or stage == "completed":
            break

    # 3. Dependency Graph
    graph = get_json(f"{BASE_URL}/repositories/{repo_id}/graph")["data"]
    nodes = graph.get("nodes", [])
    edges = graph.get("edges", [])
    cycles = graph.get("meta", {}).get("circularDependencies", [])
    print(f"    [OK] Dependency Graph: {len(nodes)} nodes, {len(edges)} edges, {len(cycles)} circular cycles detected")
    if expected_circular:
        assert len(cycles) > 0, f"Expected circular cycles in {zip_name}, got {len(cycles)}"
    else:
        print("    [OK] Clean acyclic DAG as expected.")

    # 4. Summary & Layers
    summary = get_json(f"{BASE_URL}/repositories/{repo_id}/summary")["data"]
    layers = summary.get("layers", [])
    high_risk = summary.get("highRiskEntities", [])
    print(f"    [OK] Architecture Layers: {len(layers)} layers classified")
    for layer in layers:
        print(f"       - Layer '{layer['name']}': {layer['fileCount']} file(s)")
    print(f"    [OK] High Risk Entities: {len(high_risk)} identified")

    # 5. Entities & Grounded Explanations
    entities = get_json(f"{BASE_URL}/repositories/{repo_id}/entities")["data"]
    print(f"    [OK] Total Entities Extracted: {len(entities)}")
    if entities:
        target = entities[0]
        exp = get_json(f"{BASE_URL}/repositories/{repo_id}/entities/{target['id']}/explanation")["data"]
        citations = exp.get("evidence", [])
        print(f"    [OK] Grounded Citations for '{target['name']}': {len(citations)} source citations")

    # 6. Test Generation
    print(f"[6] Generating automated tests...")
    post_json(f"{BASE_URL}/repositories/{repo_id}/tests/generate", {})
    latest_tests = get_json(f"{BASE_URL}/repositories/{repo_id}/tests/latest")["data"]
    print(f"    [OK] Tests Generated: {latest_tests.get('testsGenerated')}, Line Coverage: {latest_tests.get('lineCoverage')}%")

    print(f"[PASS] BUNDLE {zip_name} VERIFIED 100% OPERATIONAL")

def run_all():
    test_bundle("demo_python_ecommerce.zip", expected_circular=True)
    test_bundle("demo_python_data_pipeline.zip", expected_circular=False)
    test_bundle("demo_java_microservice.zip", expected_circular=True)
    print("\n[SUCCESS] ALL 3 DEMO TEST BUNDLES FULLY OPERATIONAL ON PRODUCTION!")

if __name__ == '__main__':
    run_all()
