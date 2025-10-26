// static/js/global.js - Minimal global JavaScript

// Global function to add flash messages from anywhere
window.addFlashMessage = function(type, text, duration = 5000) {
    // Flash message functionality will be added later
};

// Search functionality for header
function searchApp() {
    return {
        searchQuery: '',
        searchResults: [],
        showResults: false,
        searchTimeout: null,
        
        async searchUsers() {
            if (this.searchQuery.length < 2) {
                this.searchResults = [];
                return;
            }
            
            // Clear previous timeout
            if (this.searchTimeout) {
                clearTimeout(this.searchTimeout);
            }
            
            // Debounce search
            this.searchTimeout = setTimeout(async () => {
                try {
                    const response = await fetch(`/api/search/users?q=${encodeURIComponent(this.searchQuery)}`);
                    if (response.ok) {
                        this.searchResults = await response.json();
                    } else {
                        this.searchResults = [];
                    }
                } catch (error) {
                    console.error('Search error:', error);
                    this.searchResults = [];
                }
            }, 300);
        }
    };
}