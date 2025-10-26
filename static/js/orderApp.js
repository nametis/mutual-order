function orderApp() {
    return {
        loading: true,
        order: window.orderData || {},
        sellerInfo: {},
        myListings: [],
        otherListings: [],
        newListingUrl: '',
        flashMessage: '',
        showChat: false,
        chatMessages: [],
        newMessage: '',
        unreadCount: 0,
        currentUserId: window.currentUserId,
        isAdmin: window.isAdmin === true || window.isAdmin === 'true',
        payments: [],
        
        // New state variables
        showAdminModal: false,
        showAllMyListings: false,
        showAllOtherListings: false,
        participantSummaryData: [],
        hasFavoriteSeller: false,
        loadingFavorite: false,
        payments: [],
        
        statusSteps: [
            { key: 'building', label: 'Collecte', emoji: '⛏️' },
            { key: 'payment', label: 'Paiement', emoji: '💳' },
            { key: 'transport', label: 'Transport', emoji: '🚚' },
            { key: 'distribution', label: 'Distribution', emoji: '🎁' }
        ],
        
        adminForm: {
            direct_url: '',
            max_amount: '',
            deadline: '',
            shipping_cost: 0,
            taxes: 0,
            discount: 0,
            city: '',
            distribution_method: '',
            paypal_link: '',
            seller_shop_url: ''
        },

        async init() {
            await this.loadOrder();
            await this.loadSellerInfo();
            await this.checkFavoriteSeller();
            await this.loadParticipantSummary();
            await this.loadPayments();
            this.initAdminForm();
            this.checkUnreadMessages();

            if (this.order.status !== 'building') {
                this.loadChatMessages();
            }

            setInterval(() => this.checkUnreadMessages(), 30000);
            this.loading = false;
        },

        async loadOrder() {
            try {
                const response = await fetch(`/api/orders/${this.getOrderId()}`);
                if (response.ok) {
                    this.order = await response.json();
                    this.updateListings();
                }
            } catch (error) {
                console.error('Error loading order:', error);
            }
        },

        async loadSellerInfo() {
            try {
                const response = await fetch(`/api/sellers/${this.order.seller_name}`);
                if (response.ok) {
                    this.sellerInfo = await response.json();
                }
            } catch (error) {
                console.error('Error loading seller info:', error);
                this.sellerInfo = { rating: null, location: "Non spécifiée" };
            }
        },
        
        async checkFavoriteSeller() {
            try {
                const response = await fetch('/api/user/favorite_sellers');
                if (response.ok) {
                    const data = await response.json();
                    this.hasFavoriteSeller = (data.sellers || []).some(s => s.seller_name === this.order.seller_name);
                }
            } catch (error) {
                console.error('Error checking favorite seller:', error);
            }
        },
        
        async toggleFavoriteSeller() {
            if (this.loadingFavorite) return;
            
            this.loadingFavorite = true;
            try {
                if (this.hasFavoriteSeller) {
                    // Remove from favorites
                    const response = await fetch(`/api/user/favorite_sellers/${encodeURIComponent(this.order.seller_name)}`, {
                        method: 'DELETE'
                    });
                    if (response.ok) {
                        this.hasFavoriteSeller = false;
                    }
                } else {
                    // Add to favorites
                    const response = await fetch('/api/user/favorite_sellers', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ seller: this.order.seller_name })
                    });
                    if (response.ok) {
                        this.hasFavoriteSeller = true;
                    }
                }
            } catch (error) {
                console.error('Error toggling favorite seller:', error);
            } finally {
                this.loadingFavorite = false;
            }
        },

        async loadPayments() {
            try {
                const response = await fetch(`/api/orders/${this.getOrderId()}/payments`);
                if (response.ok) {
                    this.payments = await response.json();
                } else {
                    console.error('Failed to load payments, response:', response.status);
                    // If payments don't exist yet, initialize them
                    if (response.status === 403 || response.status === 404) {
                        await this.initializePayments();
                    }
                }
            } catch (error) {
                console.error('Error loading payments:', error);
            }
        },
        
        async initializePayments() {
            try {
                const response = await fetch(`/api/orders/${this.getOrderId()}/initialize-payments`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' }
                });
                const data = await response.json();
                if (response.ok) {
                    this.payments = data.payments || [];
                } else {
                    console.error('Failed to initialize payments:', data.error);
                }
            } catch (error) {
                console.error('Error initializing payments:', error);
            }
        },
        
        async loadParticipantSummary() {
            try {
                const response = await fetch(`/api/orders/${this.getOrderId()}/participant-summary`);
                if (response.ok) {
                    this.participantSummaryData = await response.json();
                } else {
                    // Fallback: generate from order data
                    this.participantSummaryData = this.order.participants?.map(participant => ({
                        user: participant,
                        summary: this.order.current_user_summary || {
                            listings_count: 0,
                            subtotal: 0,
                            fees_share: 0,
                            discount_share: 0,
                            total: 0
                        }
                    })) || [];
                }
            } catch (error) {
                console.error('Error loading participant summary:', error);
                this.participantSummaryData = [];
            }
        },

        updateListings() {
            this.myListings = this.order.listings?.filter(l => l.user_id === this.currentUserId) || [];
            this.otherListings = this.order.listings?.filter(l => l.user_id !== this.currentUserId) || [];
        },

        initAdminForm() {
            this.adminForm = {
                deadline: this.order.deadline ? this.order.deadline.split('T')[0] : '',
                shipping_cost: this.order.shipping_cost || 0,
                taxes: this.order.taxes || 0,
                discount: this.order.discount || 0,
                city: this.order.city || '',
                distribution_method: this.order.distribution_method || '',
                paypal_link: this.order.paypal_link || '',
                seller_shop_url: this.order.seller_shop_url || ''
            };
        },

        // --- Add / Remove / Verify Listings ---
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
                    this.flashMessage = 'Annonce ajoutée avec succès !';
                    this.newListingUrl = '';
                    await this.loadOrder();
                    await this.loadParticipantSummary();
                    setTimeout(() => this.flashMessage = '', 3000);
                } else alert(result.error || 'Erreur lors de l\'ajout');
            } catch (error) { 
                console.error('Error adding listing:', error); 
                alert('Erreur lors de l\'ajout'); 
            }
        },

        async removeListing(listingId) {
            if (!confirm('Retirer ce disque de la commande ?')) return;
            try {
                const response = await fetch(`/api/listings/${listingId}`, { method: 'DELETE' });
                if (response.ok) {
                    this.flashMessage = 'Disque retiré de la commande';
                    await this.loadOrder();
                    await this.loadParticipantSummary();
                    setTimeout(() => this.flashMessage = '', 3000);
                }
            } catch (error) { 
                console.error('Error removing listing:', error); 
            }
        },

        async verifyAvailability() {
            if (!confirm('Vérifier la disponibilité de tous les disques ?')) return;
            try {
                const response = await fetch(`/api/orders/${this.getOrderId()}/verify`, { method: 'POST' });
                const result = await response.json();
                if (response.ok) {
                    this.flashMessage = result.message || 'Vérification terminée';
                    await this.loadOrder();
                    await this.loadParticipantSummary();
                    setTimeout(() => this.flashMessage = '', 3000);
                }
            } catch (error) { 
                console.error('Error verifying availability:', error); 
            }
        },

        async updateOrderStatus(newStatus) {
            if (!confirm('Changer le statut de la commande ?')) return;
            try {
                const response = await fetch(`/api/orders/${this.getOrderId()}/status`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ status: newStatus })
                });
                const result = await response.json();
                if (response.ok) { 
                    this.flashMessage = 'Statut mis à jour avec succès'; 
                    await this.loadOrder();
                    await this.loadParticipantSummary();
                    setTimeout(() => this.flashMessage = '', 3000); 
                } else {
                    alert(result.error || 'Erreur lors de la mise à jour');
                }
            } catch (error) { 
                console.error('Error updating status:', error); 
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
                    this.flashMessage = result.message || 'Paramètres mis à jour avec succès'; 
                    this.showAdminModal = false;
                    await this.loadOrder();
                    await this.loadParticipantSummary();
                    await this.loadPayments();
                    this.initAdminForm(); // Refresh the form with new data
                    setTimeout(() => this.flashMessage = '', 3000); 
                } else {
                    alert(result.error || 'Erreur lors de la mise à jour');
                }
            } catch (error) { 
                console.error('Error updating settings:', error); 
                alert('Erreur lors de la mise à jour'); 
            }
        },

        confirmDeleteOrder() {
            // Check if order is already deleted and user is admin
            if (this.order && this.order.status === 'deleted' && window.isAdmin) {
                if (confirm('Cette commande est déjà supprimée. Voulez-vous la supprimer définitivement de la base de données ?')) {
                    this.deleteOrder();
                }
            } else {
                if (confirm('Êtes-vous sûr de vouloir supprimer cette commande ?')) {
                    this.deleteOrder();
                }
            }
        },

        async deleteOrder() {
            try {
                const response = await fetch(`/api/orders/${this.getOrderId()}`, { method: 'DELETE' });
                const result = await response.json();
                if (response.ok) { 
                    // Show success message based on the response
                    if (result.message) {
                        alert(result.message);
                    }
                    window.location.href = '/'; 
                } else {
                    alert(result.error || 'Erreur lors de la suppression');
                }
            } catch (error) { 
                console.error('Error deleting order:', error); 
                alert('Erreur lors de la suppression'); 
            }
        },


        // --- Chat functions ---
        toggleChat() {
            this.showChat = !this.showChat;
            if (this.showChat) { 
                this.loadChatMessages(); 
                this.markMessagesAsRead(); 
            }
        },

        async loadChatMessages() {
            try {
                const response = await fetch(`/api/orders/${this.getOrderId()}/chat/messages`);
                if (response.ok) {
                    this.chatMessages = await response.json();
                    this.scrollChatToBottom();
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
                }
            } catch (error) { 
                console.error('Error sending message:', error); 
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

        async markMessagesAsRead() {
            try {
                await fetch(`/api/orders/${this.getOrderId()}/chat/mark_read`, { method: 'POST' });
                this.unreadCount = 0;
            } catch (error) { 
                console.error('Error marking messages as read:', error); 
            }
        },

        // --- Utility functions ---
        shareOrder() {
            const url = window.location.href;
            try {
                if (navigator.clipboard && window.isSecureContext) {
                    navigator.clipboard.writeText(url).then(() => {
                        // Show a subtle notification instead of alert
                        const notification = document.createElement('div');
                        notification.className = 'fixed top-4 right-4 bg-green-500 text-white px-4 py-2 rounded-lg shadow-lg z-50';
                        notification.textContent = 'Lien copié !';
                        document.body.appendChild(notification);
                        setTimeout(() => {
                            document.body.removeChild(notification);
                        }, 2000);
                    });
                } else {
                    // Fallback for older browsers
                    const textArea = document.createElement('textarea');
                    textArea.value = url;
                    document.body.appendChild(textArea);
                    textArea.select();
                    document.execCommand('copy');
                    document.body.removeChild(textArea);
                    const notification = document.createElement('div');
                    notification.className = 'fixed top-4 right-4 bg-green-500 text-white px-4 py-2 rounded-lg shadow-lg z-50';
                    notification.textContent = 'Lien copié !';
                    document.body.appendChild(notification);
                    setTimeout(() => {
                        document.body.removeChild(notification);
                    }, 2000);
                }
            } catch (e) {
                // Fallback for any errors
                const textArea = document.createElement('textarea');
                textArea.value = url;
                document.body.appendChild(textArea);
                textArea.select();
                document.execCommand('copy');
                document.body.removeChild(textArea);
                const notification = document.createElement('div');
                notification.className = 'fixed top-4 right-4 bg-green-500 text-white px-4 py-2 rounded-lg shadow-lg z-50';
                notification.textContent = 'Lien copié !';
                document.body.appendChild(notification);
                setTimeout(() => {
                    document.body.removeChild(notification);
                }, 2000);
            }
        },

        getConditionClass(condition) {
            if (!condition) return 'bg-gray-100 text-gray-800';
            if (condition.includes('Mint')) return 'bg-green-100 text-green-800';
            if (condition.includes('Near Mint')) return 'bg-emerald-100 text-emerald-800';
            if (condition.includes('Very Good Plus')) return 'bg-yellow-100 text-yellow-800';
            if (condition.includes('Very Good')) return 'bg-orange-100 text-orange-800';
            if (condition.includes('Good')) return 'bg-red-100 text-red-800';
            return 'bg-gray-100 text-gray-800';
        },

        getShortCondition(condition) {
            if (!condition) return '';
            const match = condition.match(/\(([^)]+)\)/);
            if (match) return match[1];
            if (condition.includes('Mint')) return 'M';
            if (condition.includes('Near Mint')) return 'NM';
            if (condition.includes('Very Good Plus')) return 'VG+';
            if (condition.includes('Very Good')) return 'VG';
            if (condition.includes('Good Plus')) return 'G+';
            if (condition.includes('Good')) return 'G';
            if (condition.includes('Fair')) return 'F';
            if (condition.includes('Poor')) return 'P';
            return condition;
        },

        getTimeRemaining(deadline) {
            if (!deadline) return '';
            const now = new Date();
            const end = new Date(deadline);
            const diff = end - now;
            if (diff <= 0) return 'Expiré';
            const days = Math.floor(diff / (1000 * 60 * 60 * 24));
            const hours = Math.floor((diff % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60));
            if (days > 0) return `${days}j ${hours}h`;
            if (hours > 0) return `${hours}h`;
            return '<1h';
        },

        formatDate(dateString) {
            if (!dateString) return '';
            return new Date(dateString).toLocaleDateString('fr-FR', { year: 'numeric', month: '2-digit', day: '2-digit' });
        },
        
        formatOrderDate(deadline) {
            if (!deadline) return 'N/A';
            
            // Handle ISO date strings - ensure we parse as UTC and convert to local
            let date;
            if (deadline.includes('T') && deadline.includes('Z')) {
                // ISO string with Z (UTC) - parse directly
                date = new Date(deadline);
            } else if (deadline.includes('T')) {
                // ISO string without Z - treat as UTC
                date = new Date(deadline + 'Z');
            } else {
                // Fallback
                date = new Date(deadline);
            }
            
            // Check if date is valid
            if (isNaN(date.getTime())) return 'N/A';
            
            const day = date.getDate();
            const month = date.getMonth() + 1; // getMonth() returns 0-11
            
            return `${day}/${month}`;
        },
        
        getStatusDateLabel(status) {
            const labels = {
                'validation': 'En validation le',
                'ordered': 'Commandée le',
                'delivered': 'Livrée le',
                'closed': 'Distribuée le',
                'deleted': 'Supprimée le'
            };
            return labels[status] || 'Créée le';
        },

        getStepClass(stepKey, index) {
            const currentIndex = this.statusSteps.findIndex(step => step.key === this.order.status);
            if (index < currentIndex) return 'bg-green-500 text-white';
            if (index === currentIndex) return 'bg-blue-500 text-white';
            return 'bg-gray-200 text-gray-600';
        },

        isStepCompleted(stepKey) {
            const currentIndex = this.statusSteps.findIndex(step => step.key === this.order.status);
            const stepIndex = this.statusSteps.findIndex(step => step.key === stepKey);
            return stepIndex < currentIndex;
        },

        getPreviousStatus() {
            const statusOrder = ['building', 'payment', 'transport', 'distribution'];
            const currentIndex = statusOrder.indexOf(this.order.status);
            return currentIndex > 0 ? statusOrder[currentIndex - 1] : 'building';
        },

        getOrderId() {
            return window.location.pathname.split('/')[2];
        },
        
        scrollChatToBottom() {
            setTimeout(() => {
                // Scroll floating chat modal
                const floatingChat = this.$refs.chatMessages;
                if (floatingChat) {
                    floatingChat.scrollTop = floatingChat.scrollHeight;
                }
                
                // Scroll embedded chat
                const embeddedChat = this.$refs.embeddedChatMessages;
                if (embeddedChat) {
                    embeddedChat.scrollTop = embeddedChat.scrollHeight;
                }
            }, 100);
        },    
        
        // --- Payment methods ---
        getParticipantPaymentStatus(userId) {
            const payment = this.payments.find(p => p.user.id === userId);
            return payment ? payment.is_paid : false;
        },
        
        async togglePayment(userId) {
            const payment = this.payments.find(p => p.user.id === userId);
            if (!payment) {
                console.error('No payment found for user:', userId, 'Available payments:', this.payments);
                return;
            }
            
            const newStatus = !payment.is_paid;
            const endpoint = newStatus 
                ? `/api/orders/${this.getOrderId()}/payments/${payment.id}/mark-paid`
                : `/api/orders/${this.getOrderId()}/payments/${payment.id}/unmark-paid`;
            
            
            try {
                const response = await fetch(endpoint, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' }
                });
                
                let data;
                try {
                    data = await response.json();
                } catch (jsonError) {
                    console.error('Failed to parse response as JSON:', jsonError);
                    const text = await response.text();
                    console.error('Response text:', text);
                    alert('Erreur de serveur: ' + text.substring(0, 100));
                    return;
                }
                
                if (response.ok && data.success) {
                    payment.is_paid = newStatus;
                    // Force Alpine to update by reassigning the array
                    this.payments = [...this.payments];
                } else {
                    console.error('Failed to update payment:', data.error || 'Unknown error');
                    alert(data.error || 'Erreur lors de la mise à jour du paiement');
                }
            } catch (error) {
                console.error('Error toggling payment:', error);
                alert('Erreur lors de la mise à jour du paiement: ' + error.message);
            }
        },
        
        getPaymentStatusCount() {
            const paid = this.payments.filter(p => p.is_paid).length;
            return { paid, total: this.payments.length };
        },
        
        // --- Computed properties ---
        get myTotal() {
            return this.order.current_user_summary ? this.order.current_user_summary.subtotal : 0;
        },

        get myFeesShare() {
            return this.order.current_user_summary ? this.order.current_user_summary.fees_share : 0;
        },

        get myDiscountShare() {
            return this.order.current_user_summary ? this.order.current_user_summary.discount_share : 0;
        },

        get isCreator() {
            return this.order.creator_id === this.currentUserId;
        },

        get isParticipant() {
            return this.myListings.length > 0;
        },

        get showChatBlock() {
            // Show chat on step 2 (payment) or after step 3 (transport/distribution)
            const stepIndex = this.statusSteps.findIndex(s => s.key === this.order.status);
            return stepIndex >= 1;
        },

        openAllDiscsInTabs() {
            // Get all listings from all participants
            const allListings = [...this.myListings, ...this.otherListings];
            
            if (allListings.length === 0) {
                alert('Aucun disque trouvé dans cette commande');
                return;
            }

            // Show confirmation dialog
            const confirmed = confirm(`Voulez-vous ouvrir ${allListings.length} onglet${allListings.length > 1 ? 's' : ''} pour tous les disques de la commande ?\n\nNote: Votre navigateur pourrait bloquer les popups multiples.`);
            
            if (!confirmed) {
                return;
            }

            // Try to open all tabs at once first
            let openedCount = 0;
            allListings.forEach((listing, index) => {
                const newWindow = window.open(listing.listing_url, '_blank');
                if (newWindow) {
                    openedCount++;
                }
            });

            // If only one tab opened (browser blocked others), try sequential approach
            if (openedCount === 1 && allListings.length > 1) {
                const continueSequential = confirm(`Seul 1 onglet a pu s'ouvrir automatiquement.\n\nVoulez-vous ouvrir les ${allListings.length - 1} autres onglets un par un ?\n\nCliquez sur "OK" pour chaque onglet.`);
                
                if (continueSequential) {
                    this.openDiscsSequentially(allListings.slice(1));
                }
            } else {
                // Show success message
                const message = `Ouverture de ${openedCount} onglet${openedCount > 1 ? 's' : ''}...`;
                this.flashMessage = message;
                setTimeout(() => {
                    this.flashMessage = '';
                }, 3000);
            }
        },

        openDiscsSequentially(listings) {
            if (listings.length === 0) {
                this.flashMessage = 'Tous les onglets ont été ouverts !';
                setTimeout(() => {
                    this.flashMessage = '';
                }, 3000);
                return;
            }

            const listing = listings[0];
            const remaining = listings.slice(1);
            
            // Open current listing
            window.open(listing.listing_url, '_blank');
            
            // Show progress and ask to continue
            const continueNext = confirm(`Onglet ouvert pour: ${listing.title}\n\n${remaining.length} onglet${remaining.length > 1 ? 's' : ''} restant${remaining.length > 1 ? 's' : ''}.\n\nContinuer avec le suivant ?`);
            
            if (continueNext) {
                // Continue with next listing after a short delay
                setTimeout(() => {
                    this.openDiscsSequentially(remaining);
                }, 500);
            } else {
                this.flashMessage = `Ouverture interrompue. ${remaining.length} onglet${remaining.length > 1 ? 's' : ''} non ouvert${remaining.length > 1 ? 's' : ''}.`;
                setTimeout(() => {
                    this.flashMessage = '';
                }, 3000);
            }
        }
    };
}