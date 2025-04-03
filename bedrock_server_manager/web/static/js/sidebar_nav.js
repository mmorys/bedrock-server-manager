// bedrock-server-manager/bedrock_server_manager/web/static/js/sidebar_nav.js
document.addEventListener('DOMContentLoaded', () => {
    // Select all navigation links within the sidebar that have a 'data-target' attribute
    const navLinks = document.querySelectorAll('.sidebar-nav .nav-link[data-target]');

    // Select all content sections within the main content area
    const contentSections = document.querySelectorAll('.main-content .content-section');

    // Function to handle switching tabs/sections
    function switchSection(event) {
        event.preventDefault(); // Prevent default anchor link behavior

        const clickedLink = event.currentTarget;
        const targetId = clickedLink.dataset.target; // Get the ID from data-target attribute
        const targetSection = document.getElementById(targetId);

        // Only proceed if the target section actually exists
        if (targetSection) {
            // 1. Deactivate all links
            navLinks.forEach(link => {
                link.classList.remove('active');
            });

            // 2. Deactivate (hide) all content sections
            contentSections.forEach(section => {
                section.classList.remove('active');
            });

            // 3. Activate the clicked link
            clickedLink.classList.add('active');

            // 4. Activate (show) the target content section
            targetSection.classList.add('active');

            // Optional: Scroll to the top of the content area when switching
            // const mainContent = document.querySelector('.main-content');
            // if (mainContent) {
            //     mainContent.scrollTop = 0; // Or mainContent.scrollTo(0, 0);
            // }

        } else {
            console.warn(`Sidebar navigation error: Content section with ID "${targetId}" not found.`);
        }
    }

    // Attach the click event listener to each navigation link
    navLinks.forEach(link => {
        link.addEventListener('click', switchSection);
    });

    // Optional: Handle initial state based on URL hash if desired
    // This allows linking directly to a section like index.html#manage-section
    /*
    if (window.location.hash) {
        const initialTargetId = window.location.hash.substring(1); // Remove '#'
        const initialLink = document.querySelector(`.sidebar-nav .nav-link[data-target="${initialTargetId}"]`);
        if (initialLink) {
            // Simulate a click event to set the initial state correctly
            initialLink.click();
        }
    }
    */
});