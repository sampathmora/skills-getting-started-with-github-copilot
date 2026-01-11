"""
Tests for the Mergington High School API endpoints
"""

import pytest
from fastapi.testclient import TestClient
from src.app import app, activities


@pytest.fixture
def client():
    """Create a test client for the FastAPI app"""
    return TestClient(app)


@pytest.fixture(autouse=True)
def reset_activities():
    """Reset activities data before each test"""
    # Store original state with deep copy
    original_activities = {}
    for name, details in activities.items():
        original_activities[name] = {
            "description": details["description"],
            "schedule": details["schedule"],
            "max_participants": details["max_participants"],
            "participants": details["participants"].copy()
        }
    
    yield
    
    # Restore original state after test by clearing and rebuilding
    activities.clear()
    for name, details in original_activities.items():
        activities[name] = {
            "description": details["description"],
            "schedule": details["schedule"],
            "max_participants": details["max_participants"],
            "participants": details["participants"].copy()
        }


class TestRootEndpoint:
    """Tests for the root endpoint"""
    
    def test_root_redirects_to_static(self, client):
        """Test that root endpoint redirects to static/index.html"""
        response = client.get("/", follow_redirects=False)
        assert response.status_code == 307
        assert response.headers["location"] == "/static/index.html"


class TestGetActivities:
    """Tests for GET /activities endpoint"""
    
    def test_get_activities_returns_all_activities(self, client):
        """Test that all activities are returned"""
        response = client.get("/activities")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, dict)
        assert len(data) > 0
        assert "Basketball Team" in data
        assert "Programming Class" in data
    
    def test_activity_structure(self, client):
        """Test that each activity has the correct structure"""
        response = client.get("/activities")
        data = response.json()
        
        for activity_name, activity_details in data.items():
            assert "description" in activity_details
            assert "schedule" in activity_details
            assert "max_participants" in activity_details
            assert "participants" in activity_details
            assert isinstance(activity_details["participants"], list)
            assert isinstance(activity_details["max_participants"], int)


class TestSignupForActivity:
    """Tests for POST /activities/{activity_name}/signup endpoint"""
    
    def test_signup_success(self, client):
        """Test successful signup for an activity"""
        # Use an email that doesn't exist in any activity
        test_email = "newstudent@mergington.edu"
        
        response = client.post(
            f"/activities/Chess Club/signup?email={test_email}"
        )
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert test_email in data["message"]
        assert "Chess Club" in data["message"]
        
        # Verify student was added
        activities_response = client.get("/activities")
        activities_data = activities_response.json()
        assert test_email in activities_data["Chess Club"]["participants"]
    
    def test_signup_nonexistent_activity(self, client):
        """Test signup for an activity that doesn't exist"""
        response = client.post(
            "/activities/Nonexistent Club/signup?email=test@mergington.edu"
        )
        assert response.status_code == 404
        data = response.json()
        assert "detail" in data
        assert "Activity not found" in data["detail"]
    
    def test_signup_already_registered(self, client):
        """Test that a student cannot sign up for multiple activities"""
        # First signup
        response1 = client.post(
            "/activities/Chess Club/signup?email=duplicate@mergington.edu"
        )
        assert response1.status_code == 200
        
        # Try to signup for another activity
        response2 = client.post(
            "/activities/Programming Class/signup?email=duplicate@mergington.edu"
        )
        assert response2.status_code == 400
        data = response2.json()
        assert "detail" in data
        assert "already signed up" in data["detail"]
    
    def test_signup_with_special_characters_in_activity_name(self, client):
        """Test signup with URL-encoded activity name"""
        response = client.post(
            "/activities/Basketball%20Team/signup?email=player@mergington.edu"
        )
        assert response.status_code == 200 or response.status_code == 400  # May already be registered


class TestUnregisterFromActivity:
    """Tests for DELETE /activities/{activity_name}/unregister endpoint"""
    
    def test_unregister_success(self, client):
        """Test successful unregistration from an activity"""
        # First, signup a student with a unique email
        signup_email = "tounregister@mergington.edu"
        signup_response = client.post(f"/activities/Chess Club/signup?email={signup_email}")
        assert signup_response.status_code == 200
        
        # Then unregister
        response = client.delete(
            f"/activities/Chess Club/unregister?email={signup_email}"
        )
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert signup_email in data["message"]
        assert "Unregistered" in data["message"]
        
        # Verify student was removed
        activities_response = client.get("/activities")
        activities_data = activities_response.json()
        assert signup_email not in activities_data["Chess Club"]["participants"]
    
    def test_unregister_nonexistent_activity(self, client):
        """Test unregister from an activity that doesn't exist"""
        response = client.delete(
            "/activities/Nonexistent Club/unregister?email=test@mergington.edu"
        )
        assert response.status_code == 404
        data = response.json()
        assert "detail" in data
        assert "Activity not found" in data["detail"]
    
    def test_unregister_not_registered(self, client):
        """Test unregister when student is not registered for the activity"""
        response = client.delete(
            "/activities/Chess Club/unregister?email=notregistered@mergington.edu"
        )
        assert response.status_code == 400
        data = response.json()
        assert "detail" in data
        assert "not registered" in data["detail"]
    
    def test_unregister_existing_participant(self, client):
        """Test unregistering an existing participant"""
        # Get an activity with existing participants
        activities_response = client.get("/activities")
        activities_data = activities_response.json()
        
        # Find an activity with participants
        for activity_name, details in activities_data.items():
            if len(details["participants"]) > 0:
                existing_email = details["participants"][0]
                
                # Unregister
                response = client.delete(
                    f"/activities/{activity_name}/unregister?email={existing_email}"
                )
                assert response.status_code == 200
                
                # Verify removal
                updated_response = client.get("/activities")
                updated_data = updated_response.json()
                assert existing_email not in updated_data[activity_name]["participants"]
                break


class TestIntegrationScenarios:
    """Integration tests for complete user workflows"""
    
    def test_complete_signup_and_unregister_workflow(self, client):
        """Test a complete workflow of signup and unregister"""
        test_email = "workflow@mergington.edu"
        activity_name = "Drama Club"
        
        # Get initial participant count
        initial_response = client.get("/activities")
        initial_count = len(initial_response.json()[activity_name]["participants"])
        
        # Signup
        signup_response = client.post(
            f"/activities/{activity_name}/signup?email={test_email}"
        )
        assert signup_response.status_code == 200
        
        # Verify signup
        after_signup = client.get("/activities")
        assert len(after_signup.json()[activity_name]["participants"]) == initial_count + 1
        assert test_email in after_signup.json()[activity_name]["participants"]
        
        # Unregister
        unregister_response = client.delete(
            f"/activities/{activity_name}/unregister?email={test_email}"
        )
        assert unregister_response.status_code == 200
        
        # Verify unregister
        after_unregister = client.get("/activities")
        assert len(after_unregister.json()[activity_name]["participants"]) == initial_count
        assert test_email not in after_unregister.json()[activity_name]["participants"]
    
    def test_cannot_signup_twice_for_same_activity(self, client):
        """Test that double signup for same activity is prevented"""
        test_email = "double@mergington.edu"
        
        # First signup
        response1 = client.post(
            "/activities/Art Studio/signup?email=double@mergington.edu"
        )
        assert response1.status_code == 200
        
        # Try to signup again for the same activity
        response2 = client.post(
            "/activities/Art Studio/signup?email=double@mergington.edu"
        )
        assert response2.status_code == 400
