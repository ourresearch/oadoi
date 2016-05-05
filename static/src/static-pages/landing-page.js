angular.module('staticPages', [
    'ngRoute',
    'satellizer',
    'ngMessages'
])

    .config(function ($routeProvider) {
        $routeProvider.when('/', {
            templateUrl: "static-pages/landing.tpl.html",
            controller: "LandingPageCtrl",
            resolve: {
                isLoggedIn: function($auth, $q, $location){
                    var deferred = $q.defer()
                    if ($auth.isAuthenticated()){
                        var url = "/u/" + $auth.getPayload().sub
                        $location.path(url)
                    }
                    else {
                        return $q.when(true)

                        deferred.resolve()
                    }

                    return deferred.promise
                }
            }
        })
    })


    

    .config(function ($routeProvider) {
        $routeProvider.when('/login', {
            templateUrl: "static-pages/login.tpl.html",
            controller: "LoginCtrl"
        })
    })

    .config(function ($routeProvider) {
        $routeProvider.when('/twitter-login', {
            templateUrl: "static-pages/twitter-login.tpl.html",
            controller: "TwitterLoginCtrl"
        })
    })

    .controller("TwitterLoginCtrl", function($scope){
        console.log("twitter page controller is running!")

    })


    .controller("LoginCtrl", function ($scope, $location, $http, $auth, $rootScope, Person) {
        console.log("kenny loggins page controller is running!")


        var searchObject = $location.search();
        var code = searchObject.code
        if (!code){
            $location.path("/")
            return false
        }

        var requestObj = {
            code: code,
            redirectUri: window.location.origin + "/login"
        }

        $http.post("api/auth/orcid", requestObj)
            .success(function(resp){
                console.log("got a token back from ye server", resp)
                $auth.setToken(resp.token)
                var payload = $auth.getPayload()

                $rootScope.sendCurrentUserToIntercom()
                $location.url("u/" + payload.sub)
            })
            .error(function(resp){
              console.log("problem getting token back from server!", resp)
                $location.url("/")
            })






    })

    .controller("LandingPageCtrl", function ($scope,
                                             $mdDialog,
                                             $rootScope,
                                             $timeout) {
        $scope.global.showBottomStuff = false;
        console.log("landing page!", $scope.global)

        var orcidModalCtrl = function($scope){
            console.log("IHaveNoOrcidCtrl ran" )
            $scope.modalAuth = function(){
                $mdDialog.hide()
            }
        }

        $scope.noOrcid = function(ev){
            $mdDialog.show({
                controller: orcidModalCtrl,
                templateUrl: 'orcid-dialog.tmpl.html',
                clickOutsideToClose:true,
                targetEvent: ev
            })
                .then(
                function(){
                    $rootScope.authenticate("signin")
                },
                function(){
                    console.log("they cancelled the dialog")
                }
            )


        }

    })
    .controller("IHaveNoOrcidCtrl", function($scope){
        console.log("IHaveNoOrcidCtrl ran" )
    })










