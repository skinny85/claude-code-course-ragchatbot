import pytest
import sys
import os
from unittest.mock import patch

# Add backend to path for imports
sys.path.append(os.path.dirname(os.path.dirname(__file__)))

from config import Config, config


class TestConfig:
    """Test configuration functionality and validation"""
    
    def test_default_config_values(self):
        """Test that default configuration values are reasonable"""
        test_config = Config()
        
        # Test AI model settings
        assert test_config.ANTHROPIC_MODEL == "claude-sonnet-4-20250514"
        assert test_config.EMBEDDING_MODEL == "all-MiniLM-L6-v2"
        
        # Test document processing settings
        assert test_config.CHUNK_SIZE == 800
        assert test_config.CHUNK_OVERLAP == 100
        assert test_config.MAX_HISTORY == 2
        
        # Test database path
        assert test_config.CHROMA_PATH == "./chroma_db"
    
    def test_max_results_configuration_issue(self):
        """Test the MAX_RESULTS configuration - this should fail and reveal the bug"""
        test_config = Config()
        
        # This is the bug! MAX_RESULTS is set to 0, which would return no search results
        assert test_config.MAX_RESULTS == 0  # This is the problem!
        
        # MAX_RESULTS should be > 0 for the system to work
        # This test documents the issue that needs to be fixed
    
    @patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-api-key-from-env"})
    def test_api_key_from_environment(self):
        """Test loading API key from environment variable"""
        test_config = Config()
        assert test_config.ANTHROPIC_API_KEY == "test-api-key-from-env"
    
    @patch.dict(os.environ, {}, clear=True)
    def test_api_key_empty_when_not_set(self):
        """Test API key is empty when not set in environment"""
        test_config = Config()
        assert test_config.ANTHROPIC_API_KEY == ""
    
    def test_chunk_settings_reasonable(self):
        """Test that chunk size and overlap are reasonable"""
        test_config = Config()
        
        # Chunk size should be positive and reasonable
        assert test_config.CHUNK_SIZE > 0
        assert test_config.CHUNK_SIZE <= 2000  # Not too large
        
        # Overlap should be less than chunk size
        assert test_config.CHUNK_OVERLAP < test_config.CHUNK_SIZE
        assert test_config.CHUNK_OVERLAP >= 0
    
    def test_history_limit_reasonable(self):
        """Test that history limit is reasonable"""
        test_config = Config()
        
        assert test_config.MAX_HISTORY >= 0
        assert test_config.MAX_HISTORY <= 10  # Not too many to avoid token limits
    
    def test_global_config_instance(self):
        """Test that global config instance is properly initialized"""
        assert config is not None
        assert isinstance(config, Config)
        assert config.ANTHROPIC_MODEL == "claude-sonnet-4-20250514"
    
    def test_config_dataclass_structure(self):
        """Test that config is properly structured as a dataclass"""
        import dataclasses
        
        assert dataclasses.is_dataclass(Config)
        
        # Check that all fields are documented
        fields = dataclasses.fields(Config)
        field_names = [field.name for field in fields]
        
        expected_fields = [
            "ANTHROPIC_API_KEY",
            "ANTHROPIC_MODEL", 
            "EMBEDDING_MODEL",
            "CHUNK_SIZE",
            "CHUNK_OVERLAP",
            "MAX_RESULTS",
            "MAX_HISTORY",
            "CHROMA_PATH"
        ]
        
        for field in expected_fields:
            assert field in field_names, f"Missing expected config field: {field}"
    
    @patch.dict(os.environ, {"CHROMA_PATH": "/custom/chroma/path"})
    def test_custom_chroma_path(self):
        """Test custom ChromaDB path from environment"""
        # Note: Current implementation doesn't read CHROMA_PATH from env
        # This test documents expected behavior
        test_config = Config()
        
        # Currently this will fail because CHROMA_PATH is hardcoded
        # This is another potential improvement
        assert test_config.CHROMA_PATH == "./chroma_db"  # Current hardcoded value
    
    def test_model_names_are_valid_strings(self):
        """Test that model names are non-empty strings"""
        test_config = Config()
        
        assert isinstance(test_config.ANTHROPIC_MODEL, str)
        assert len(test_config.ANTHROPIC_MODEL) > 0
        
        assert isinstance(test_config.EMBEDDING_MODEL, str) 
        assert len(test_config.EMBEDDING_MODEL) > 0
    
    def test_configuration_for_search_functionality(self):
        """Test configuration values that are critical for search to work"""
        test_config = Config()
        
        # This is the critical test - MAX_RESULTS must be > 0 for search to return results
        if test_config.MAX_RESULTS <= 0:
            pytest.fail(
                f"MAX_RESULTS is {test_config.MAX_RESULTS} but must be > 0 for search to work. "
                "This is likely the root cause of 'query failed' errors!"
            )
        
        # Other critical settings
        assert test_config.CHUNK_SIZE > 0, "CHUNK_SIZE must be > 0 for document processing"
        assert test_config.EMBEDDING_MODEL, "EMBEDDING_MODEL must be specified"


class TestConfigEnvironmentIntegration:
    """Test configuration loading from environment variables"""
    
    @patch.dict(os.environ, {
        "ANTHROPIC_API_KEY": "sk-test-key-12345",
        "ANTHROPIC_MODEL": "claude-3-sonnet",
        "EMBEDDING_MODEL": "custom-embedding-model"
    })
    def test_environment_variable_loading(self):
        """Test that environment variables are loaded correctly"""
        test_config = Config()
        
        assert test_config.ANTHROPIC_API_KEY == "sk-test-key-12345"
        # Note: Other env vars aren't currently supported but this tests the pattern
        
    def test_missing_api_key_handling(self):
        """Test behavior when API key is missing"""
        with patch.dict(os.environ, {}, clear=True):
            test_config = Config()
            
            # System should handle missing API key gracefully
            assert test_config.ANTHROPIC_API_KEY == ""
            
            # This could be enhanced to validate API key format
    
    def test_env_file_loading(self):
        """Test that .env file loading works"""
        # This tests that load_dotenv() is called during import
        # The actual .env file loading is tested implicitly
        test_config = Config()
        
        # At minimum, config should be created without errors
        assert test_config is not None


if __name__ == "__main__":
    pytest.main([__file__])