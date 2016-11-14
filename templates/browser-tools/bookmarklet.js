// injected into the site by the oaDOI bookmarklet link.

(function() {


    // development settings and tools
    var devMode = true;
    var baseUrl = "{{ base_url }}"

    // default for if this is not being served by Flask
    if (baseUrl.indexOf("base_url") > 0){
        baseUrl = "https://oadoi.org/static/browser-tools/"
    }

    var devLog = function(str, obj){
        if (devMode){
            console.log("oaDOI: " + str, obj)
        }
    }

    // other config vars

    // from https://help.altmetric.com/support/solutions/articles/6000086842-getting-started-with-altmetric-on-your-journal-books-or-institutional-repository
    var doiMetaNames = [
        "citation_doi",
        "doi",
        "dc.doi",
        "dc.identifier",
        "dc.identifier.doi",
        "bepress_citation_doi",
        "rft_id"
    ]

    // templates
    var loadingSpinner
    loadingSpinner = '<svg width="20px" height="20px" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100" preserveAspectRatio="xMidYMid" class="uil-ring"><rect x="0" y="0" width="100" height="100" fill="none" class="bk"></rect><circle cx="50" cy="50" r="40" stroke-dasharray="163.36281798666926 87.9645943005142" stroke="#ffffff" fill="none" stroke-width="20"><animateTransform attributeName="transform" type="rotate" values="0 50 50;180 50 50;360 50 50;" keyTimes="0;0.5;1" dur="1s" repeatCount="indefinite" begin="0s"></animateTransform></circle></svg>'
    //loadingSpinner = "<img src='"+ baseUrl + "spinner.gif"  +"'>"


    var mainTemplate = "<div id='oaDOI-main' class='loading'>" +
            "<a id='oaDOI-logo-link' href='https://oadoi.org'><img src='https://oadoi.org/static/img/oadoi-logo-white.png'></a>" +
            "<div id='oaDOI-msg'>" +
                "<span id='oaDOI-msg-text'>" + loadingSpinner + "Looking for open versions...</span> " +
            "</div>" +
            "<a href='' id='oaDOI-close-btn'>&#215;</a>" +
        "</div>"



    function init() {
        devLog("running oaDOI bookmarklet.")
        var $ = jQuery;

        // define functions that use jQuery

        function reportResult(result){
            devLog("reporting result: " + result)
            var errorReportLink = "<a href='mailto:team@impactstory.org' class='oaDOI-msg-report-error'>(report error)</a>"
            var results = {
                "no-doi": {
                    msg: "Sorry, we couldn't find a DOI on this page.",
                    showErrorLink: true
                },
                "no-open-version": {
                    msg: "Sorry, we couldn't find an open version of this article.",
                    showErrorLink: true
                },
                "viewing-open-version": {
                    msg: "Looks like you're currently viewing an open-access version of this article.",
                    showErrorLink: true
                },
                "found-open-version": {
                    msg: "Found one! Redirecting you...",
                    showErrorLink: false
                }
            }

            var myResult = results[result];

            $("#oaDOI-msg-text").text(myResult.msg)
            if (myResult.showErrorLink){
                $("#oaDOI-msg").append(errorReportLink)
            }
            $("#oaDOI-main")
                .removeClass("loading")
                .addClass("has-result")
                .addClass("result-" + result)
            return true
        }


        function findDoi(){
            var doi

            // look in the meta tags
            $("meta").each(function(i, myMeta){

                // has to be a meta name likely to contain a DOI
                if (doiMetaNames.indexOf(myMeta.name.toLowerCase()) < 0) {
                    return // continue iterating
                }
                // content has to look like a  DOI.
                // much room for improvement here.
                var doiCandidate = myMeta.content.replace("doi:", "").trim()
                if (doiCandidate.indexOf("10.") === 0) {
                    doi = doiCandidate
                }
            })

            if (doi){
                return doi
            }

            // look in the document string
            var docAsStr = document.documentElement.innerHTML;

            // ScienceDirect pages
            // http://www.sciencedirect.com/science/article/pii/S1751157709000881
            var scienceDirectRegex = /SDM.doi\s*=\s*'([^']+)'/;
            var m = scienceDirectRegex.exec(docAsStr)
            if (m && m.length > 1){
                devLog("found a ScienceDirect DOI", m)
                return m[1]
            }

            // sniff doi from the altmetric.com widget
            var altmetricWidgetDoi = /data-doi\s*=\s*'([^']+)'/;


            return null

        }





        // procedural part of the code

        // inject our markup.

        $("#oaDOI-main").remove()
        $(mainTemplate)
            .hide()
            .height("77px")
            .prependTo("body")
            .slideDown(250)
            .find("#oaDOI-close-btn")
            .click(function(){
                $("#oaDOI-main").slideUp(100)
                return false
        })



        // find a DOI
        var doi = findDoi()


        // report the result to the user

        console.log("doi:", doi)
        if (!doi){
            reportResult("no-doi")
            return false
        }
        var url = "https://api.oadoi.org/" + doi
        $.get(url, function(data){

            var resp = data.results[0]
            devLog("got data back from oaDOI", data)

            if (!resp.free_fulltext_url) {
                reportResult("no-open-version")
            }
            else if (resp.oa_color == "gold"){
                reportResult("viewing-open-version")
            }
            else {
                reportResult("found-open-version")
                window.location.assign(resp.free_fulltext_url)
            }

        })


    }



    // runs when you click the bookmarklet

    // inject our stylesheet
    var elem = document.createElement("link");
    elem.type = "text/css";
    elem.rel = "stylesheet";
    elem.href = baseUrl + "bookmarklet.css";
    var head = document.getElementsByTagName("head")[0]
    head.appendChild(elem);

    // load jquery
    if (typeof jQuery=='undefined') {
        console.log("no jquery. adding it.")
        var jq = document.createElement( 'script' );
        jq.type = 'text/javascript';
        //jq.async = true;
        jq.onload=init
        jq.src = 'https://ajax.googleapis.com/ajax/libs/jquery/3.1.1/jquery.min.js';
        document.body.appendChild(jq);
    }
    else {
        console.log("looks like we've got jquery.")
        init();
    }





})();