#!/usr/bin/env python3
"""
Test script for incremental update functionality via web API
"""

import requests
import json
import time

# Configuration
API_BASE = "http://localhost:8080"

def test_incremental_update():
    """Test the incremental update functionality"""
    
    print("🔬 Testing Incremental Update Web API...")
    
    # Test health endpoint
    print("\n1. Testing health endpoint...")
    try:
        response = requests.get(f"{API_BASE}/health")
        if response.status_code == 200:
            print("✅ API is healthy")
        else:
            print(f"⚠️ API health check returned: {response.status_code}")
    except requests.exceptions.ConnectionError:
        print("❌ Cannot connect to API. Make sure web server is running on port 8080")
        return False
    
    # List available projects
    print("\n2. Listing available projects...")
    try:
        response = requests.get(f"{API_BASE}/api/projects")
        data = response.json()
        
        if data.get('projects'):
            projects = data['projects']
            print(f"📁 Found {len(projects)} projects: {', '.join(projects)}")
            
            if projects:
                test_project = projects[0]
                print(f"🎯 Using project '{test_project}' for testing")
                
                # Test incremental update
                print(f"\n3. Testing incremental update for '{test_project}'...")
                
                update_payload = {
                    "project": test_project,
                    "force_update": False
                }
                
                response = requests.post(
                    f"{API_BASE}/api/update",
                    headers={"Content-Type": "application/json"},
                    json=update_payload
                )
                
                if response.status_code == 200:
                    result = response.json()
                    
                    if result.get('error'):
                        print(f"❌ Update error: {result['error']}")
                    elif result.get('status') == 'up_to_date':
                        print("✅ Project is already up to date")
                        print(f"   📊 Unchanged files: {result.get('unchanged_files', 0)}")
                    else:
                        print("✅ Incremental update completed")
                        print(f"   📝 Processed files: {result.get('processed_files', 0)}")
                        print(f"   🆕 New files: {result.get('new_files', 0)}")
                        print(f"   🔄 Modified files: {result.get('modified_files', 0)}")
                        print(f"   🗑️ Removed files: {result.get('removed_files', 0)}")
                        print(f"   📊 Updated chunks: {result.get('updated_chunks', 0)}")
                        print(f"   🗑️ Removed chunks: {result.get('removed_chunks', 0)}")
                        print(f"   ⏸️ Unchanged files: {result.get('unchanged_files', 0)}")
                        
                        if result.get('errors'):
                            print(f"   ⚠️ Errors: {len(result['errors'])}")
                    
                    return True
                else:
                    print(f"❌ Update request failed: {response.status_code}")
                    print(f"Response: {response.text}")
                    return False
            else:
                print("❌ No projects found to test")
                return False
        else:
            print("❌ Failed to get projects list")
            return False
            
    except Exception as e:
        print(f"❌ Error during testing: {e}")
        return False

def test_force_update():
    """Test force update functionality"""
    
    print("\n🔬 Testing Force Update...")
    
    # Get first project
    try:
        response = requests.get(f"{API_BASE}/api/projects")
        data = response.json()
        
        if data.get('projects'):
            test_project = data['projects'][0]
            print(f"🎯 Force updating project '{test_project}'...")
            
            update_payload = {
                "project": test_project,
                "force_update": True
            }
            
            response = requests.post(
                f"{API_BASE}/api/update",
                headers={"Content-Type": "application/json"},
                json=update_payload
            )
            
            if response.status_code == 200:
                result = response.json()
                
                if result.get('error'):
                    print(f"❌ Force update error: {result['error']}")
                else:
                    print("✅ Force update completed")
                    print(f"   📝 Processed files: {result.get('processed_files', 0)}")
                    print(f"   📊 Updated chunks: {result.get('updated_chunks', 0)}")
                
                return True
            else:
                print(f"❌ Force update failed: {response.status_code}")
                return False
        else:
            print("❌ No projects available for force update test")
            return False
            
    except Exception as e:
        print(f"❌ Error during force update test: {e}")
        return False

if __name__ == "__main__":
    print("🧪 CodeRAG Incremental Update Web API Test")
    print("=" * 50)
    
    success = test_incremental_update()
    
    if success:
        print("\n" + "=" * 50)
        test_force_update()
    
    print("\n" + "=" * 50)
    print("💡 To use the web interface:")
    print(f"   1. Make sure the web API is running: python web_api.py")
    print(f"   2. Open browser: {API_BASE}")
    print(f"   3. Go to 'Update' tab")
    print(f"   4. Select a project and click 'Update'")
    print("\n🎉 Test completed!")