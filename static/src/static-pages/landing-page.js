angular.module('staticPages', [
    'ngRoute',
    'satellizer',
    'ngMessages'
])

    .config(function ($routeProvider) {
        $routeProvider.when('/', {
            templateUrl: "static-pages/landing.tpl.html",
            controller: "LandingPageCtrl"
        })
    })

    

    .config(function ($routeProvider) {
        $routeProvider.when('/login', {
            templateUrl: "static-pages/login.tpl.html",
            controller: "LoginCtrl"
        })
    })



    .controller("LoginCtrl", function ($scope, $location, $http, $auth) {
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
                var created = moment(payload.created).unix()
                var intercomInfo = {
                    app_id: "z93rnxrs",
                    name: payload.given_names + " " + payload.family_name,
                    user_id: payload.sub, // orcid ID
                    created_at: created
                  }

                Intercom('boot', intercomInfo)
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
                $rootScope.authenticate("signin")
            }
        }

        $scope.noOrcid = function(){
            $mdDialog.show({
                controller: orcidModalCtrl,
                templateUrl: 'orcid-dialog.tmpl.html',
                clickOutsideToClose:true
            })


        }

    })
    .controller("IHaveNoOrcidCtrl", function($scope){
        console.log("IHaveNoOrcidCtrl ran" )
    })










