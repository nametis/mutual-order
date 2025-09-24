// static/js/global.js - Minimal global JavaScript
console.log('Global.js loaded');

// Global function to add flash messages from anywhere
window.addFlashMessage = function(type, text, duration = 5000) {
    console.log(`Flash ${type}: ${text}`);
    // Flash message functionality will be added later
};