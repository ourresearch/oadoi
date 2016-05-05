angular.module('settingsPage', [
    'ngRoute'
])



    .config(function($routeProvider) {
        $routeProvider.when('/me/settings', {
            templateUrl: 'settings-page/settings-page.tpl.html',
            controller: 'settingsPageCtrl',
            resolve: {
                isAuth: function($q, $auth){
                    if ($auth.isAuthenticated()){
                        return $q.resolve()
                    }
                    else {
                        return $q.reject("/settings only works if you're logged in.")
                    }
                }
            }
        })
    })



    .controller("settingsPageCtrl", function($scope, $rootScope, $auth, $route, $location, $http, Person){

        console.log("the settings page loaded")
        var myOrcidId = $auth.getPayload().sub
        $scope.orcidId = myOrcidId
        $scope.givenNames = $auth.getPayload()["given_names"]

        $scope.wantToDelete = false
        $scope.deleteProfile = function() {
            $http.delete("/api/me")
                .success(function(resp){
                    // let Intercom know
                    window.Intercom("update", {
                        user_id: myOrcidId,
                        is_deleted: true
                    })


                    $auth.logout()
                    $location.path("/")
                    alert("Your profile has been deleted.")
                })
                .error(function(){
                    alert("Sorry, something went wrong!")
                })
        }


        $scope.syncState = 'ready'

        $scope.pullFromOrcid = function(){
            console.log("ah, refreshing!")
            $scope.syncState = "working"
            $http.post("/api/person/" + myOrcidId)
                .success(function(resp){
                    // force a reload of the person
                    Intercom('trackEvent', 'synced');
                    Intercom('trackEvent', 'synced-to-edit');
                    Person.load(myOrcidId, true).then(
                        function(resp){
                            $scope.syncState = "success"
                            console.log("we reloaded the Person after sync")
                            $rootScope.sendToIntercom(resp)
                        }
                    )
                })
        }

    })












