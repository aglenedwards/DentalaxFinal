// Praxis-Formular-Fixes - Modernisierte Version
document.addEventListener('DOMContentLoaded', function() {
  console.log('Praxis Form Fix geladen!');
  
  // Helfer-Funktion zur Aktualisierung der Fortschrittsanzeige
  function updateProgress(stepId) {
    // Schrittnummer extrahieren (z.B. "step2" -> 2)
    const stepNumber = parseInt(stepId.replace('step', ''));
    
    // Prozentwert berechnen (6 Schritte insgesamt)
    const progressPercent = (stepNumber / 6) * 100;
    
    // Fortschrittsbalken aktualisieren
    const progressBar = document.getElementById('praxisFormProgress');
    if (progressBar) {
      progressBar.style.width = progressPercent + '%';
      progressBar.setAttribute('aria-valuenow', progressPercent);
      progressBar.textContent = 'Schritt ' + stepNumber + ' von 6';
    }
  }
  
  // Helfer-Funktion zur Aktualisierung der Schrittkreise
  function updateStepCircles(currentStep) {
    // Alle Schritte durchgehen
    for (let i = 1; i <= 6; i++) {
      const stepElement = document.querySelector('.progress-step[data-step="' + i + '"]');
      if (stepElement) {
        // Aktuelle und vorherige Schritte markieren
        if (i < currentStep) {
          stepElement.classList.add('completed');
          stepElement.classList.remove('active');
        } else if (i === currentStep) {
          stepElement.classList.add('active');
          stepElement.classList.remove('completed');
        } else {
          stepElement.classList.remove('active', 'completed');
        }
      }
    }
  }
  
  // Alle "Weiter"-Buttons verarbeiten
  const nextButtons = document.querySelectorAll('.next-step');
  nextButtons.forEach(button => {
    console.log('Weiter-Button gefunden für:', button.getAttribute('data-target'));
    
    button.addEventListener('click', function(event) {
      // Tab-ID aus data-target (z.B. "step2-tab")
      const targetTabId = this.getAttribute('data-target');
      console.log('Weiter-Button geklickt für Tab:', targetTabId);
      
      // Tab-Element finden
      const tabButton = document.getElementById(targetTabId);
      
      // Tab aktivieren
      if (tabButton) {
        console.log('Aktiviere Tab:', targetTabId);
        
        // Bootstrap's Tab-Aktivierung auslösen
        const tabTrigger = new bootstrap.Tab(tabButton);
        tabTrigger.show();
        
        // Formular-Schritt aktualisieren
        const formStepInput = document.getElementById('form_step');
        if (formStepInput) {
          // "step2-tab" zu "step2" konvertieren
          const stepNumber = targetTabId.replace('-tab', '');
          formStepInput.value = stepNumber;
          console.log('Form step aktualisiert zu:', formStepInput.value);
          
          // Fortschrittsanzeige aktualisieren
          updateProgress(stepNumber);
        }
        
        // Die aktuelle Schrittnummer aus dem Tab-ID extrahieren
        const currentStep = parseInt(targetTabId.match(/\d+/)[0]);
        
        // Alle vorherigen Schritte als abgeschlossen markieren
        updateStepCircles(currentStep);
      } else {
        console.error('Tab-Button nicht gefunden:', targetTabId);
      }
    });
  });
  
  // Alle "Zurück"-Buttons verarbeiten
  const prevButtons = document.querySelectorAll('.prev-step');
  prevButtons.forEach(button => {
    button.addEventListener('click', function(event) {
      const targetTabId = this.getAttribute('data-target');
      const tabButton = document.getElementById(targetTabId);
      
      if (tabButton) {
        const tabTrigger = new bootstrap.Tab(tabButton);
        tabTrigger.show();
        
        const formStepInput = document.getElementById('form_step');
        if (formStepInput) {
          const stepNumber = targetTabId.replace('-tab', '');
          formStepInput.value = stepNumber;
          
          // Fortschrittsanzeige aktualisieren
          updateProgress(stepNumber);
          
          // Die aktuelle Schrittnummer aus dem Tab-ID extrahieren
          const currentStep = parseInt(targetTabId.match(/\d+/)[0]);
          
          // Kreise aktualisieren
          updateStepCircles(currentStep);
        }
      }
    });
  });
  
  // Den Final-Submit-Button neu konfigurieren
  const finalSubmitBtn = document.getElementById('finalSubmitBtn');
  const praxisdatenForm = document.getElementById('praxisdatenForm');
  
  if (finalSubmitBtn && praxisdatenForm) {
    console.log('Final Submit Button gefunden!');
    
    // Neuen Event-Listener hinzufügen
    finalSubmitBtn.addEventListener('click', function(event) {
      event.preventDefault(); // Standard-Submit verhindern
      console.log('Final Submit Button geklickt!');
      
      // Letzten Schritt als aktiven Schritt setzen
      document.getElementById('form_step').value = 'step6';
      
      // Hidden input für final submit
      let finalSubmitInput = document.getElementById('final_submit');
      if (!finalSubmitInput) {
        finalSubmitInput = document.createElement('input');
        finalSubmitInput.type = 'hidden';
        finalSubmitInput.name = 'final_submit';
        finalSubmitInput.id = 'final_submit';
        praxisdatenForm.appendChild(finalSubmitInput);
      }
      finalSubmitInput.value = '1';
      
      // Tracking-Info hinzufügen
      let submitTracker = document.getElementById('praxisform_submit_timestamp');
      if (!submitTracker) {
        submitTracker = document.createElement('input');
        submitTracker.type = 'hidden';
        submitTracker.name = 'praxisform_submit_timestamp';
        submitTracker.id = 'praxisform_submit_timestamp';
        praxisdatenForm.appendChild(submitTracker);
      }
      submitTracker.value = Date.now().toString();
      
      // Debug-Informationen
      console.log('FINAL SUBMIT: Formular wird abgesendet!');
      console.log('form_step:', document.getElementById('form_step').value);
      console.log('final_submit:', '1');
      console.log('Formular-URL:', praxisdatenForm.action);
      
      // Formular absenden
      praxisdatenForm.submit();
    });
  } else {
    console.error('Final Submit Button oder Formular nicht gefunden!');
  }
  
  // Initialisierung - Den ersten Schritt aktivieren und Fortschritt auf aktuelle Tab setzen
  const initialStep = document.getElementById('form_step').value || 'step1';
  updateProgress(initialStep);
  const currentStep = parseInt(initialStep.match(/\d+/)[0]);
  updateStepCircles(currentStep);
});

// Zusätzliche Funktionen für die kachelförmige Terminbuchungsauswahl
document.addEventListener('DOMContentLoaded', function() {
  // Karten als Optionenauswahl
  const bookingCards = document.querySelectorAll('.booking-option-card');
  const bookingRadios = document.querySelectorAll('input[name="terminbuchung_modus"]');
  const redirectUrlContainer = document.getElementById('terminbuchung_url_container');
  const apiConfigContainer = document.getElementById('api_config_container');
  
  // Initialisierung des aktiven Zustands
  function initializeActiveBookingCard() {
    const activeValue = Array.from(bookingRadios).find(radio => radio.checked)?.value || 'dashboard';
    bookingCards.forEach(card => {
      if (card.dataset.option === activeValue) {
        card.classList.add('selected');
      } else {
        card.classList.remove('selected');
      }
    });
    
    // Ein-/Ausblenden der zugehörigen Container
    updateConfigContainers(activeValue);
  }
  
  // Helfer-Funktion zum Aktualisieren der Konfigurations-Container
  function updateConfigContainers(value) {
    if (value === 'redirect') {
      redirectUrlContainer.style.display = 'block';
      apiConfigContainer.style.display = 'none';
    } else if (value === 'api') {
      redirectUrlContainer.style.display = 'none';
      apiConfigContainer.style.display = 'block';
    } else {
      redirectUrlContainer.style.display = 'none';
      apiConfigContainer.style.display = 'none';
    }
  }
  
  // Karten als klickbare Elemente konfigurieren
  bookingCards.forEach(card => {
    card.addEventListener('click', function() {
      const option = this.dataset.option;
      
      // Radio-Button auswählen
      const radio = document.getElementById('terminbuchung_modus_' + option);
      if (radio) {
        radio.checked = true;
        
        // Visuelle Auswahl aktualisieren
        bookingCards.forEach(c => c.classList.remove('selected'));
        this.classList.add('selected');
        
        // Container aktualisieren
        updateConfigContainers(option);
      }
    });
  });
  
  // Auch bei direkter Auswahl der Radio-Buttons
  bookingRadios.forEach(radio => {
    radio.addEventListener('change', function() {
      initializeActiveBookingCard();
    });
  });
  
  // API-Schlüssel generieren
  const generateApiKeyBtn = document.getElementById('generate_api_key');
  if (generateApiKeyBtn) {
    generateApiKeyBtn.addEventListener('click', function() {
      const apiKeyInput = document.getElementById('api_key');
      if (apiKeyInput) {
        // Zufälligen API-Schlüssel generieren (24 Zeichen)
        const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789';
        let apiKey = '';
        for (let i = 0; i < 24; i++) {
          apiKey += chars.charAt(Math.floor(Math.random() * chars.length));
        }
        apiKeyInput.value = apiKey;
      }
    });
  }
  
  // Endpunkte kopieren
  const copyButtons = document.querySelectorAll('.copy-btn');
  copyButtons.forEach(btn => {
    btn.addEventListener('click', function() {
      const endpoint = this.dataset.endpoint;
      
      // Text in die Zwischenablage kopieren
      navigator.clipboard.writeText(endpoint).then(() => {
        // Bestätigung anzeigen
        const originalText = this.innerHTML;
        this.innerHTML = '<i class="fas fa-check"></i>';
        
        setTimeout(() => {
          this.innerHTML = originalText;
        }, 1500);
      });
    });
  });
  
  // Initial aktiven Status setzen
  initializeActiveBookingCard();
});

// Konfigurationsanzeige für Terminbuchungsoptionen in eigenem Tab
document.addEventListener('DOMContentLoaded', function() {
  // Referenzen zu den Konfigurationsbereichen
  const redirectConfig = document.getElementById('redirect_config');
  const apiConfig = document.getElementById('api_config');
  const formularConfig = document.getElementById('formular_config');
  const dashboardConfig = document.getElementById('dashboard_config');
  
  // Funktion zum Anzeigen der richtigen Konfiguration basierend auf der ausgewählten Option
  function updateConfigVisibility() {
    // Alle Konfigurationsbereiche ausblenden
    if (redirectConfig) redirectConfig.style.display = 'none';
    if (apiConfig) apiConfig.style.display = 'none';
    if (formularConfig) formularConfig.style.display = 'none';
    if (dashboardConfig) dashboardConfig.style.display = 'none';
    
    // Den ausgewählten Konfigurationsbereich anzeigen
    const selectedOption = document.querySelector('input[name="terminbuchung_modus"]:checked');
    if (selectedOption) {
      const option = selectedOption.value;
      
      if (option === 'redirect' && redirectConfig) {
        redirectConfig.style.display = 'block';
      } else if (option === 'api' && apiConfig) {
        apiConfig.style.display = 'block';
      } else if (option === 'formular' && formularConfig) {
        formularConfig.style.display = 'block';
      } else if (option === 'dashboard' && dashboardConfig) {
        dashboardConfig.style.display = 'block';
      }
    }
  }
  
  // Bei Änderung der Terminbuchungsoption die Konfigurationsanzeige aktualisieren
  const terminbuchungRadios = document.querySelectorAll('input[name="terminbuchung_modus"]');
  terminbuchungRadios.forEach(radio => {
    radio.addEventListener('change', updateConfigVisibility);
  });
  
  // Initial die richtige Konfiguration anzeigen
  updateConfigVisibility();
  
  // Kachelkarten als klickbare Elemente
  const bookingCards = document.querySelectorAll('.booking-option-card');
  bookingCards.forEach(card => {
    card.addEventListener('click', function() {
      // Kachelkartendarstellung aktualisieren
      bookingCards.forEach(c => c.classList.remove('selected'));
      this.classList.add('selected');
      
      // Zugehöriges Radio-Button auswählen
      const option = this.dataset.option;
      const radio = document.getElementById('terminbuchung_modus_' + option);
      if (radio) {
        radio.checked = true;
        
        // Konfigurationsanzeige aktualisieren
        updateConfigVisibility();
      }
    });
  });
  
  // API-Schlüssel generieren
  const generateApiKeyBtn = document.getElementById('generate_api_key');
  if (generateApiKeyBtn) {
    generateApiKeyBtn.addEventListener('click', function() {
      const apiKeyInput = document.getElementById('api_key');
      if (apiKeyInput) {
        // Zufälligen API-Schlüssel generieren (24 Zeichen)
        const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789';
        let apiKey = '';
        for (let i = 0; i < 24; i++) {
          apiKey += chars.charAt(Math.floor(Math.random() * chars.length));
        }
        apiKeyInput.value = apiKey;
      }
    });
  }
  
  // Endpunkte kopieren
  const copyButtons = document.querySelectorAll('.copy-btn');
  copyButtons.forEach(btn => {
    btn.addEventListener('click', function() {
      const endpoint = this.dataset.endpoint;
      
      // Text in die Zwischenablage kopieren
      navigator.clipboard.writeText(endpoint).then(() => {
        // Bestätigung anzeigen
        const originalText = this.innerHTML;
        this.innerHTML = '<i class="fas fa-check"></i>';
        
        setTimeout(() => {
          this.innerHTML = originalText;
        }, 1500);
      });
    });
  });
});
