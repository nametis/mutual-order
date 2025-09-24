// static/js/order-app-v2.js - Modular Alpine.js approach with shared data

// Global state store that all components can access
window.orderStore = {
    // Data
    loading: true,
    order: {},
    sellerInfo: {},
    validations: [],
    chatMessages: [],
    unreadCount: 0,
    currentUserId: window.currentUserId,
    isAdmin: window.isAdmin,
    
    // UI State
    showOrderSummary: false,
    showChat: false,
    editField: null,
    flashMessage: '',
    flashType: '',
    showMoreSettings: false,
    
    // Form data
    newListingUrl: '',
    newMessage: '',
    validationAgreement: false,
    userValidated: false,
    
    // Admin form
    adminForm: {
        direct_url: '',
        max_amount: '',
        deadline: '',
        payment_timing: 'avant la commande',
        shipping_cost: 0,
        taxes: 0,
        discount: 0,
        user_location: '',
        paypal_link: ''
    },
    
    // Status steps
    statusSteps: [
        { key: 'building', label: 'Composition', emoji: '⛏️' },
        { key: 'validation', label: 'Validation', emoji: '⏳' },
        { key: 'ordered', label: 'Commandé', emoji: '✅' },
        { key: 'delivered', label: 'Livré', emoji: '💿' },
        { key: 'closed', label: 'Distribué', emoji: '🎁' }
    ],
    
    // Methods
    async init() {
        console.log('Initializing order store...');
        try {
            await this.loadOrderData();
            await this.loadSellerInfo();
            await this.loadValidations();
            this.initAdminForm();
            this.startPeriodicTasks();
            
            if (this.order.status !== 'building') {
                this.loadChatMessages();
            }
        } catch (error) {
            console.error('Failed to initialize:', error);
            this.showFlash('Erreur lors du chargement', 'danger');
        } finally {
            this.loading = false;
        }
    },
    
    async loadOrderData() {
        const orderId = this.getOrderId();
        const response = await fetch(`/api/orders/${orderId}`);
        
        if (!response.ok) {
            throw new Error('Failed to load order data');
        }
        
        this.order = await response.json();
    },
    
    async loadSellerInfo() {
        try {
            const response = await fetch(`/api/sellers/${this.order.seller_name}`);
            if (response.ok) {
                this.sellerInfo = await response.json();
            }
        } catch (error) {
            console.warn('Failed to load seller info:', error);
            this.sellerInfo = { rating: null, location: 'Non spécifiée' };
        }
    },
    
    async loadValidations() {
        try {
            const response = await fetch(`/api/orders/${this.getOrderId()}/validation-status`);
            if (response.ok) {
                const data = await response.json();
                this.userValidated = data.user_validated;
                this.validations = data.all_validations || [];
            }
        } catch (error) {
            console.error('Error loading validations:', error);
        }
    },
    
    initAdminForm() {
        this.adminForm = {
            direct_url: this.order.direct_url || '',
            max_amount: this.order.max_amount || '',
            deadline: this.order.deadline ? this.order.deadline.split('T')[0] : '',
            payment_timing: this.order.payment_timing || 'avant la commande',
            shipping_cost: this.order.shipping_cost || 0,
            taxes: this.order.taxes || 0,
            discount: this.order.discount || 0,
            user_location: this.order.user_location || '',
            paypal_link: this.order.paypal_link || ''
        };
    },
    
    startPeriodicTasks() {
        setInterval(() => this.checkUnreadMessages(), 30000);
        this.checkUnreadMessages();
    },
    
    // Listings
    get myListings() {
        return this.order.listings?.filter(l => l.user_id === this.currentUserId) || [];
    },
    
    get otherListings() {
        return this.order.listings?.filter(l => l.user_id !== this.currentUserId) || [];
    },
    
    async addListing() {
        if (!this.newListingUrl.trim()) return;
        
        try {
            const response = await fetch(`/api/orders/${this.getOrderId()}/listings`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ listing_url: this.newListingUrl })
            });
            
            const result = await response.json();
            if (response.ok) {
                this.showFlash('Annonce ajoutée avec succès !', 'success');
                this.newListingUrl = '';
                await this.loadOrderData();
            } else {
                this.showFlash(result.error || 'Erreur lors de l\'ajout', 'danger');
            }
        } catch (error) {
            console.error('Error adding listing:', error);
            this.showFlash('Erreur de connexion', 'danger');
        }
    },
    
    async removeListing(listingId) {
        try {
            const response = await fetch(`/api/listings/${listingId}`, {
                method: 'DELETE'
            });
            
            if (response.ok) {
                this.showFlash('Disque retiré de la commande', 'success');
                await this.loadOrderData();
            } else {
                this.showFlash('Erreur lors de la suppression', 'danger');
            }
        } catch (error) {
            console.error('Error removing listing:', error);
            this.showFlash('Erreur de connexion', 'danger');
        }
    },
    
    // Order management
    async updateOrderStatus(newStatus) {
        try {
            const response = await fetch(`/api/orders/${this.getOrderId()}/status`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ status: newStatus })
            });
            
            const result = await response.json();
            if (response.ok) {
                this.showFlash('Statut mis à jour avec succès', 'success');
                await this.loadOrderData();
            } else {
                this.showFlash(result.error || 'Erreur lors de la mise à jour', 'danger');
            }
        } catch (error) {
            console.error('Error updating status:', error);
            this.showFlash('Erreur de connexion', 'danger');
        }
    },
    
    async updateOrderSettings() {
        try {
            const response = await fetch(`/api/orders/${this.getOrderId()}/settings`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(this.adminForm)
            });
            
            const result = await response.json();
            if (response.ok) {
                this.showFlash(result.message || 'Paramètres mis à jour avec succès', 'success');
                await this.loadOrderData();
            } else {
                this.showFlash(result.error || 'Erreur lors de la mise à jour', 'danger');
            }
        } catch (error) {
            console.error('Error updating settings:', error);
            this.showFlash('Erreur de connexion', 'danger');
        }
    },
    
    // Chat
    async loadChatMessages() {
        try {
            const response = await fetch(`/api/orders/${this.getOrderId()}/chat/messages`);
            if (response.ok) {
                this.chatMessages = await response.json();
            }
        } catch (error) {
            console.error('Error loading chat messages:', error);
        }
    },
    
    async sendMessage() {
        if (!this.newMessage.trim()) return;
        
        try {
            const response = await fetch(`/api/orders/${this.getOrderId()}/chat/send`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ message: this.newMessage })
            });
            
            if (response.ok) {
                this.newMessage = '';
                await this.loadChatMessages();
            } else {
                this.showFlash('Erreur lors de l\'envoi du message', 'danger');
            }
        } catch (error) {
            console.error('Error sending message:', error);
            this.showFlash('Erreur de connexion', 'danger');
        }
    },
    
    async checkUnreadMessages() {
        if (this.showChat) return;
        
        try {
            const response = await fetch(`/api/orders/${this.getOrderId()}/chat/unread`);
            if (response.ok) {
                const data = await response.json();
                this.unreadCount = data.unread_count;
            }
        } catch (error) {
            console.error('Error checking unread messages:', error);
        }
    },
    
    // Validation
    async validateUserParticipation() {
        if (!this.validationAgreement) return;
        
        try {
            const response = await fetch(`/api/orders/${this.getOrderId()}/validate`, {
                method: 'POST'
            });
            
            const result = await response.json();
            if (response.ok) {
                this.userValidated = true;
                this.showFlash('Participation validée avec succès', 'success');
                await this.loadValidations();
                await this.loadOrderData();
            } else {
                this.showFlash(result.error || 'Erreur lors de la validation', 'danger');
            }
        } catch (error) {
            console.error('Error validating participation:', error);
            this.showFlash('Erreur de connexion', 'danger');
        }
    },
    
    isParticipantValidated(participantId) {
        return this.validations.some(v => v.user_id === participantId && v.validated);
    },
    
    // Utilities
    showFlash(message, type = 'info', duration = 3000) {
        this.flashMessage = message;
        this.flashType = type;
        
        if (window.addFlashMessage) {
            window.addFlashMessage(type, message, duration);
        }
        
        setTimeout(() => {
            this.flashMessage = '';
            this.flashType = '';
        }, duration);
    },
    
    getOrderId() {
        return window.location.pathname.split('/')[2];
    },
    
    // Computed properties
    get isCreator() {
        return this.order.creator_id === this.currentUserId;
    },
    
    get isParticipant() {
        return this.myListings.length > 0;
    }
};

// Main Alpine.js component that initializes everything
function orderApp() {
    return {
        // Reference to global store
        ...window.orderStore,
        
        // Initialize the app
        async init() {
            await window.orderStore.init();
        }
    };
}

// Component-specific Alpine.js functions that access the global store
function orderInfoComponent() {
    return {
        get order() { return window.orderStore.order; },
        get sellerInfo() { return window.orderStore.sellerInfo; },
        get editField() { return window.orderStore.editField; },
        set editField(value) { window.orderStore.editField = value; },
        get showOrderSummary() { return window.orderStore.showOrderSummary; },
        set showOrderSummary(value) { window.orderStore.showOrderSummary = value; },
        get currentUserId() { return window.orderStore.currentUserId; },
        get isAdmin() { return window.orderStore.isAdmin; }
    };
}

function listingsComponent() {
    return {
        get order() { return window.orderStore.order; },
        get myListings() { return window.orderStore.myListings; },
        get otherListings() { return window.orderStore.otherListings; },
        get currentUserId() { return window.orderStore.currentUserId; },
        get isAdmin() { return window.orderStore.isAdmin; },
        get newListingUrl() { return window.orderStore.newListingUrl; },
        set newListingUrl(value) { window.orderStore.newListingUrl = value; },
        
        async addListing() {
            await window.orderStore.addListing();
        },
        
        async removeListing(listingId) {
            await window.orderStore.removeListing(listingId);
        },
        
        getConditionClass(condition) {
            if (!condition) return 'bg-gray-100 text-gray-800';
            const conditionLower = condition.toLowerCase();
            if (conditionLower.includes('mint') && !conditionLower.includes('near')) {
                return 'bg-green-100 text-green-800';
            } else if (conditionLower.includes('near mint')) {
                return 'bg-emerald-100 text-emerald-800';
            } else if (conditionLower.includes('very good plus')) {
                return 'bg-yellow-100 text-yellow-800';
            } else if (conditionLower.includes('very good')) {
                return 'bg-orange-100 text-orange-800';
            } else if (conditionLower.includes('good')) {
                return 'bg-red-100 text-red-800';
            }
            return 'bg-gray-100 text-gray-800';
        },
        
        getShortCondition(condition) {
            if (!condition) return '';
            const match = condition.match(/\(([^)]+)\)/);
            if (match) return match[1];
            return condition.substring(0, 3).toUpperCase();
        }
    };
}

function statusComponent() {
    return {
        get order() { return window.orderStore.order; },
        get statusSteps() { return window.orderStore.statusSteps; },
        get currentUserId() { return window.orderStore.currentUserId; },
        get isAdmin() { return window.orderStore.isAdmin; },
        
        async updateOrderStatus(newStatus) {
            await window.orderStore.updateOrderStatus(newStatus);
        },
        
        getStepClass(stepKey, index) {
            const currentIndex = this.statusSteps.findIndex(step => step.key === this.order.status);
            if (index < currentIndex) {
                return 'bg-green-500 text-white';
            } else if (index === currentIndex) {
                return 'bg-blue-500 text-white';
            } else {
                return 'bg-gray-200 text-gray-600';
            }
        },
        
        isStepCompleted(stepKey) {
            const currentIndex = this.statusSteps.findIndex(step => step.key === this.order.status);
            const stepIndex = this.statusSteps.findIndex(step => step.key === stepKey);
            return stepIndex < currentIndex;
        },
        
        getPreviousStatus() {
            const statusOrder = ['building', 'validation', 'ordered', 'delivered', 'closed'];
            const currentIndex = statusOrder.indexOf(this.order.status);
            return currentIndex > 0 ? statusOrder[currentIndex - 1] : 'building';
        }
    };
}

function participantsComponent() {
    return {
        get order() { return window.orderStore.order; },
        get unreadCount() { return window.orderStore.unreadCount; },
        get showChat() { return window.orderStore.showChat; },
        set showChat(value) { window.orderStore.showChat = value; },
        
        toggleChat() {
            window.orderStore.showChat = !window.orderStore.showChat;
            if (window.orderStore.showChat) {
                window.orderStore.loadChatMessages();
            }
        }
    };
}

function summaryComponent() {
    return {
        get order() { return window.orderStore.order; }
    };
}

function adminComponent() {
    return {
        get order() { return window.orderStore.order; },
        get adminForm() { return window.orderStore.adminForm; },
        get showMoreSettings() { return window.orderStore.showMoreSettings; },
        set showMoreSettings(value) { window.orderStore.showMoreSettings = value; },
        get currentUserId() { return window.orderStore.currentUserId; },
        get isAdmin() { return window.orderStore.isAdmin; },
        
        async updateOrderSettings() {
            await window.orderStore.updateOrderSettings();
        }
    };
}

function validationComponent() {
    return {
        get order() { return window.orderStore.order; },
        get myListings() { return window.orderStore.myListings; },
        get validationAgreement() { return window.orderStore.validationAgreement; },
        set validationAgreement(value) { window.orderStore.validationAgreement = value; },
        get userValidated() { return window.orderStore.userValidated; },
        get validations() { return window.orderStore.validations; },
        get currentUserId() { return window.orderStore.currentUserId; },
        
        async validateUserParticipation() {
            await window.orderStore.validateUserParticipation();
        },
        
        isParticipantValidated(participantId) {
            return window.orderStore.isParticipantValidated(participantId);
        },
        
        get isCreator() {
            return window.orderStore.isCreator;
        },
        
        get isParticipant() {
            return window.orderStore.isParticipant;
        }
    };
}

function chatComponent() {
    return {
        get order() { return window.orderStore.order; },
        get chatMessages() { return window.orderStore.chatMessages; },
        get newMessage() { return window.orderStore.newMessage; },
        set newMessage(value) { window.orderStore.newMessage = value; },
        get unreadCount() { return window.orderStore.unreadCount; },
        
        async sendMessage() {
            await window.orderStore.sendMessage();
        },
        
        scrollChatToBottom() {
            setTimeout(() => {
                const container = document.querySelector('[x-ref="embeddedChatMessages"]');
                if (container) {
                    container.scrollTop = container.scrollHeight;
                }
            }, 100);
        }
    };
}

function modalsComponent() {
    return {
        get showChat() { return window.orderStore.showChat; },
        get editField() { return window.orderStore.editField; },
        set editField(value) { window.orderStore.editField = value; },
        get adminForm() { return window.orderStore.adminForm; },
        get chatMessages() { return window.orderStore.chatMessages; },
        get newMessage() { return window.orderStore.newMessage; },
        set newMessage(value) { window.orderStore.newMessage = value; },
        
        toggleChat() {
            window.orderStore.showChat = !window.orderStore.showChat;
        },
        
        async sendMessage() {
            await window.orderStore.sendMessage();
        },
        
        async updateOrderSettings() {
            await window.orderStore.updateOrderSettings();
        }
    };
}