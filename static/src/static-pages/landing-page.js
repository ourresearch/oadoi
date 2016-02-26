angular.module('staticPages', [
    'ngRoute',
    'satellizer',
    'currentUserService',
    'ngMessages'
])

    .config(function ($routeProvider) {
        $routeProvider.when('/', {
            templateUrl: "static-pages/landing.tpl.html",
            controller: "LandingPageCtrl"
        })
    })


    .config(function ($routeProvider) {
        $routeProvider.when('/about', {
            templateUrl: "static-pages/about.tpl.html",
            controller: "AboutPageCtrl"
        })
    })

    .config(function ($routeProvider) {
        $routeProvider.when('/login', {
            templateUrl: "static-pages/login.tpl.html",
            controller: "LoginPageCtrl"
        })
    })


    .controller("AboutPageCtrl", function ($scope, $sce, $http, ngProgress) {

    })


    .controller("LoginPageCtrl", function ($scope, $sce, $http, ngProgress) {
        console.log("login page controller is running!")

    })

    .controller("LandingPageCtrl", function ($scope, $http, $auth, $location, ngProgress, CurrentUser) {
        console.log("landing page!")
        ngProgress.complete()

        $scope.d = {}
        $scope.d.iHaveAnOrcid = null

        var orcidSearchInProgress = false


        // trigger stuff as soon as we have CurrentUser info
        $scope.$watch("currentUser.d.email", function(newVal){
            console.log("new currentUser.d value ", newVal)
            if (_.isEmpty(CurrentUser.d)){
                console.log("no currentuser.d")
                // there is no currentUser loaded yet. don't redirect anywhere.
                return
            }

            // we can't show the landing page to logged-in people who have working profiles
            if (CurrentUser.d.orcid_id) {
                $location.path("/p/" + CurrentUser.d.orcid_id)
            }
            else {
                console.log("you ain't got no ORCID, and we got to fix that.", CurrentUser.d)
                if (orcidSearchInProgress){
                    return
                }
                orcidSearchInProgress = true


                // for testing
                // CurrentUser.d.given_names = "Elizabeth"
                // CurrentUser.d.family_name = "Williams"

                CurrentUser.d.given_names = "Ethan"
                CurrentUser.d.family_name = "White"


                var url = "/api/orcid-search?" + "given_names=" + CurrentUser.d.given_names + "&family_name=" + CurrentUser.d.family_name
                $http.get(url).success(
                    function(resp){
                        console.log("got stuff back from the ORCID search", resp)
                        $scope.orcidSearchResults = resp.list
                    }
                )
                    .error(function(msg){
                        console.log("got an error back from ORCID search", msg)
                    })
                    .finally(function(msg){
                        orcidSearchInProgress = false
                    })
            }
        })



        $scope.authenticate = function (service) {
            console.log("authenticate!")

            $auth.authenticate(service)
                .then(function(){
                    console.log("you have successfully logged in!")
                })
                .catch(function(error){
                    console.log("there was an error logging in:", error)
                })
        };


        $scope.setOrcid = function(orcid){
            console.log("setting my orcid id", orcid)
            $http.post("/api/me/orcid/" + orcid,{})
                .success(function(resp){
                    console.log("we set the orcid!", resp)
                    $location.path("/p/" + orcid)
                })
                .error(function(resp){
                    console.log("tried to set the orcid, no dice", resp)
                })
        }




        //$scope.newUser = {
        //    givenName: "",
        //    familyName: "",
        //    email: "",
        //    password: ""
        //};

    })










